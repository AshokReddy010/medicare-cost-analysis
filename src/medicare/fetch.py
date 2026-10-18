"""Download CMS "Medicare Inpatient Hospitals - by Provider and Service" and normalise every year to one schema.

The file list comes from the data.gov catalog (CKAN API), so new years are picked up automatically; a pinned
list is the fallback when the catalog is unreachable. Each yearly CSV (~150k rows: one row per hospital per
diagnosis-related group) is cleaned and written as data/raw/inpatient_<year>.parquet.

Column names changed between releases (Rndrng_CCN vs Rndrng_Prvdr_CCN, letter case), so columns are matched
by alias, and a release with a column we cannot place fails loudly instead of loading silently wrong.

    python -m medicare.fetch                     every available year
    python -m medicare.fetch --years 2019 2024
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import re
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

log = logging.getLogger("medicare")
CATALOG = "https://catalog.data.gov/api/3/action/package_show?id=medicare-inpatient-hospitals-by-provider-and-service"
UA = "medicare-cost-analysis/1.0 (https://github.com/AshokReddy010/medicare-cost-analysis)"

# Pinned in October 2026 from the catalog; used only if the catalog cannot be read.
PINNED = {
    2024: "https://data.cms.gov/sites/default/files/2026-04/828defb5-c9e6-4442-8c1b-f27bc0799daf/MUP_INP_RY26_P03_V10_DY24_PrvSvc.CSV",
    2023: "https://data.cms.gov/sites/default/files/2025-05/ca1c9013-8c7c-4560-a4a1-28cf7e43ccc8/MUP_INP_RY25_P03_V10_DY23_PrvSvc.CSV",
    2022: "https://data.cms.gov/sites/default/files/2024-05/7d1f4bcd-7dd9-4fd1-aa7f-91cd69e452d3/MUP_INP_RY24_P03_V10_DY22_PrvSvc.CSV",
    2021: "https://data.cms.gov/sites/default/files/2023-05/a754bf0b-0c51-4daf-876e-272f90a11c05/MUP_IHP_RY23_P03_V10_DY21_PRVSVC.CSV",
    2020: "https://data.cms.gov/sites/default/files/2023-05/e57818f2-318c-4979-a612-c91eba44b011/MUP_IHP_RY23_P03_V10_DY20_PRVSVC.CSV",
    2019: "https://data.cms.gov/sites/default/files/2023-05/6602e715-b301-4a38-954d-b8d5aec12b87/MUP_IHP_RY23_P03_V10_DY19_PRVSVC.CSV",
    2018: "https://data.cms.gov/sites/default/files/2023-05/78d80cf4-fc5b-40db-8e88-ca44bc86102f/MUP_IHP_RY23_P03_V10_DY18_PRVSVC.CSV",
    2017: "https://data.cms.gov/sites/default/files/2023-05/ec9287b0-68e6-4818-8c64-3a0c68fcde49/MUP_IHP_RY23_P03_V10_DY17_PRVSVC.CSV",
    2016: "https://data.cms.gov/sites/default/files/2023-05/4f20bce0-607a-46c1-bd0d-78021b0624ec/MUP_IHP_RY23_P03_V10_DY16_PRVSVC.CSV",
    2015: "https://data.cms.gov/sites/default/files/2023-05/81895338-4c5c-4ad7-a490-8e5a9a972825/MUP_IHP_RY23_P03_V10_DY15_PRVSVC.CSV",
    2014: "https://data.cms.gov/sites/default/files/2023-05/dd6961c6-0eed-4a33-8527-8f66638819b8/MUP_IHP_RY23_P03_V10_DY14_PRVSVC.CSV",
    2013: "https://data.cms.gov/sites/default/files/2023-05/3748379f-baf7-494d-abb7-653fc85176a3/MUP_IHP_RY23_P03_V10_DY13_PRVSVC.CSV",
}

# standard name -> accepted source names (compared case-insensitively)
ALIASES = {
    "ccn": ["rndrng_prvdr_ccn", "rndrng_ccn"],
    "provider_name": ["rndrng_prvdr_org_name"],
    "street": ["rndrng_prvdr_st"],
    "city": ["rndrng_prvdr_city"],
    "state": ["rndrng_prvdr_state_abrvtn"],
    "state_fips": ["rndrng_prvdr_state_fips"],
    "zip5": ["rndrng_prvdr_zip5"],
    "ruca": ["rndrng_prvdr_ruca"],
    "ruca_desc": ["rndrng_prvdr_ruca_desc"],
    "drg_code": ["drg_cd"],
    "drg_desc": ["drg_desc"],
    "discharges": ["tot_dschrgs"],
    "avg_covered_charges": ["avg_submtd_cvrd_chrg"],
    "avg_total_payment": ["avg_tot_pymt_amt"],
    "avg_medicare_payment": ["avg_mdcr_pymt_amt"],
}
REQUIRED = [
    "ccn",
    "provider_name",
    "state",
    "drg_code",
    "drg_desc",
    "discharges",
    "avg_covered_charges",
    "avg_total_payment",
    "avg_medicare_payment",
]
NUMERIC = ["discharges", "avg_covered_charges", "avg_total_payment", "avg_medicare_payment", "ruca"]


class SchemaError(ValueError):
    """A release does not have the columns this pipeline knows how to load."""


def _get(url: str, timeout: float = 300, retries: int = 4) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return bytes(r.read())
        except Exception as error:  # network errors come in many types
            last = error
            time.sleep(5 * 2**attempt)
    raise RuntimeError(f"could not download {url}: {last}")


def year_of(url: str) -> int | None:
    m = re.search(r"_DY(\d{2})_", url, re.I)
    return 2000 + int(m.group(1)) if m else None


def discover() -> dict[int, str]:
    """{data year: CSV URL} from the catalog, falling back to the pinned list."""
    try:
        pkg = json.loads(_get(CATALOG, timeout=60, retries=2))["result"]
        found = {}
        for res in pkg.get("resources", []):
            url = res.get("url", "")
            y = year_of(url)
            if y and url.lower().endswith(".csv"):
                found[y] = url
        if found:
            log.info("catalog lists %d yearly files (%d-%d)", len(found), min(found), max(found))
            return dict(sorted(found.items()))
    except Exception as error:
        log.warning("catalog unavailable (%s); using the pinned file list", error)
    return dict(PINNED)


def normalise(raw: pd.DataFrame, year: int) -> pd.DataFrame:
    lower = {c.lower().strip(): c for c in raw.columns}
    out = pd.DataFrame()
    missing = []
    for std, names in ALIASES.items():
        src = next((lower[n] for n in names if n in lower), None)
        if src is None:
            if std in REQUIRED:
                missing.append(std)
            out[std] = None
        else:
            out[std] = raw[src]
    if missing:
        raise SchemaError(f"{year}: cannot find columns for {missing}; got {list(raw.columns)}")
    for c in NUMERIC:
        out[c] = pd.to_numeric(out[c].astype(str).str.replace(r"[$,\s]", "", regex=True), errors="coerce")
    out["ccn"] = out["ccn"].astype(str).str.strip().str.zfill(6)
    out["drg_code"] = out["drg_code"].astype(str).str.strip().str.zfill(3)
    for c in ("provider_name", "street", "city", "state", "drg_desc", "ruca_desc"):
        out[c] = out[c].astype("string").str.strip()
    out["zip5"] = out["zip5"].astype("string").str.strip().str.zfill(5)
    out["state_fips"] = out["state_fips"].astype("string").str.strip().str.zfill(2)
    out.insert(0, "data_year", year)
    return out


def fetch(years: list[int] | None, out_dir: Path, force: bool = False) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    urls = discover()
    wanted = {y: u for y, u in urls.items() if not years or y in years}
    written = []
    for y, url in wanted.items():
        target = out_dir / f"inpatient_{y}.parquet"
        if target.exists() and not force:
            log.info("%s already downloaded", target.name)
            written.append(target)
            continue
        log.info("downloading %d: %s", y, url)
        raw = pd.read_csv(io.BytesIO(_get(url)), dtype=str, encoding="latin-1", keep_default_na=False, na_values=[""])
        df = normalise(raw, y)
        df.to_parquet(target, index=False)
        log.info("%d: %s rows, %s hospitals, %s DRGs", y, f"{len(df):,}", df["ccn"].nunique(), df["drg_code"].nunique())
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--years", type=int, nargs="*")
    p.add_argument("--out", type=Path, default=Path("data/raw"))
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    fetch(args.years, args.out, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
