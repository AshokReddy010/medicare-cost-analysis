import json
import os
import shutil
import subprocess
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from medicare import fetch
from medicare.export import export
from medicare.fixtures import raw_release, write_fixture

ROOT = Path(__file__).resolve().parents[1]


def test_year_of():
    assert fetch.year_of(fetch.PINNED[2024]) == 2024
    assert fetch.year_of(fetch.PINNED[2013]) == 2013
    assert fetch.year_of("https://x/other.csv") is None


def test_normalise_maps_aliases_and_types():
    raw = raw_release(2021, hospitals=5).rename(columns={"Rndrng_Prvdr_CCN": "RNDRNG_CCN", "DRG_Cd": "drg_cd"})
    raw.loc[0, "Avg_Tot_Pymt_Amt"] = "$12,345.60"
    raw.loc[0, "DRG_Cd" if "DRG_Cd" in raw else "drg_cd"] = "65"
    df = fetch.normalise(raw, 2021)
    assert list(df.columns[:3]) == ["data_year", "ccn", "provider_name"]
    assert df.loc[0, "avg_total_payment"] == 12345.6
    assert df.loc[0, "drg_code"] == "065" and df["ccn"].str.len().eq(6).all()
    assert df["data_year"].eq(2021).all()


def test_normalise_rejects_unknown_layout():
    raw = raw_release(2021, hospitals=2).drop(columns=["Avg_Tot_Pymt_Amt"])
    with pytest.raises(fetch.SchemaError, match="avg_total_payment"):
        fetch.normalise(raw, 2021)


def test_discover_falls_back_to_pinned(monkeypatch):
    monkeypatch.setattr(fetch, "_get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    assert fetch.discover() == fetch.PINNED


def test_discover_reads_catalog(monkeypatch):
    doc = {
        "result": {
            "resources": [
                {"url": fetch.PINNED[2023]},
                {"url": fetch.PINNED[2024]},
                {"url": "https://data.cms.gov/data-api/v1/dataset/x/data"},
            ]
        }
    }
    monkeypatch.setattr(fetch, "_get", lambda *a, **k: json.dumps(doc).encode())
    assert list(fetch.discover()) == [2023, 2024]


def test_fetch_skips_existing_files(tmp_path, monkeypatch):
    write_fixture(tmp_path, years=(2023,))
    monkeypatch.setattr(fetch, "discover", lambda: {2023: "u", 2024: "v"})
    csv = raw_release(2024, hospitals=3).to_csv(index=False).encode("latin-1")
    calls = []
    monkeypatch.setattr(fetch, "_get", lambda url, **k: calls.append(url) or csv)
    out = fetch.fetch(None, tmp_path)
    assert calls == ["v"] and [p.name for p in out] == ["inpatient_2023.parquet", "inpatient_2024.parquet"]
    assert pd.read_parquet(out[1])["data_year"].eq(2024).all()


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """The real dbt project built on the fixture release (needs dbt-duckdb)."""
    if not shutil.which("dbt"):
        pytest.skip("dbt not installed")
    tmp = tmp_path_factory.mktemp("build")
    raw = tmp / "raw"
    write_fixture(raw)
    env = {**os.environ, "MEDICARE_RAW": str(raw), "MEDICARE_DB": str(tmp / "m.duckdb")}
    res = subprocess.run(
        ["dbt", "build", "--profiles-dir", ".", "--target-path", str(tmp / "target")],
        cwd=ROOT / "warehouse",
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout[-3000:]
    return tmp / "m.duckdb"


def test_dbt_marts(built):
    con = duckdb.connect(str(built), read_only=True)
    years = [r[0] for r in con.execute("select data_year from mart_national_year order by 1").fetchall()]
    assert years == [2022, 2023, 2024]
    idx = con.execute("select sum(total_payment)/sum(expected_payment) from fct_provider_drg_year").fetchone()[0]
    assert abs(idx - 1) < 1e-9
    # the fixture's high-wage states should come out above the national index, low-wage below
    st = dict(con.execute("select state, payment_index from mart_state_year where data_year = 2024").fetchall())
    assert st["CA"] > 1 > st["AL"]


def test_export(built, tmp_path):
    f = export(built, tmp_path)
    assert f["latest_year"] == 2024 and f["rankable_hospitals"] > 0
    files = {p.name for p in tmp_path.iterdir()}
    assert files == {
        "meta.json",
        "national.json",
        "states.json",
        "areas.json",
        "drgs.json",
        "drg_hospitals.json",
        "hospitals.json",
        "findings.json",
    }
    meta = json.loads((tmp_path / "meta.json").read_text())
    det = json.loads((tmp_path / "drg_hospitals.json").read_text())
    assert set(meta["top_drgs"]) == set(det) and all(len(v) >= 30 for v in det.values())
    hosp = json.loads((tmp_path / "hospitals.json").read_text())
    assert hosp["columns"][1] == "name" and len(hosp["rows"]) == 40


def test_readme_findings_are_generated(built, tmp_path):
    from medicare.readme import END, START, update

    export(built, tmp_path / "data")
    readme = tmp_path / "README.md"
    readme.write_text(f"intro\n{START}\nold\n{END}\noutro\n")
    update(readme, tmp_path / "data")
    text = readme.read_text()
    assert "\nold\n" not in text and "What the data shows" in text and text.endswith("outro\n")
