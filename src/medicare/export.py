"""Publish the marts as compact JSON for the dashboard (site/data/), plus a findings summary.

Everything the page shows comes from these files, and every number in them comes from the dbt marts, so
the dashboard, the README findings and the warehouse cannot drift apart.

    python -m medicare.export --db build/medicare.duckdb --out site/data
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

TOP_DRGS = 30  # DRGs with hospital-level detail in the explorer
MIN_DRG_HOSPITALS = 30  # spreads are only meaningful with enough hospitals


def rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, r, strict=True)) for r in rel.fetchall()]


def r(x: Any, n: int = 3) -> Any:
    return None if x is None else round(float(x), n)


def export(db: Path, out: Path) -> dict[str, Any]:
    con = duckdb.connect(str(db), read_only=True)
    out.mkdir(parents=True, exist_ok=True)
    latest = con.execute("select max(data_year) from mart_national_year").fetchone()[0]  # type: ignore[index]

    national = rows(con, "select * from mart_national_year order by data_year")
    nat = [
        {
            "year": n["data_year"],
            "hospitals": n["hospitals"],
            "drgs": n["drgs"],
            "discharges": n["discharges"],
            "payment": r(n["total_payment"], 0),
            "medicare_share": r(n["medicare_share"], 4),
            "per_discharge": r(n["payment_per_discharge"], 0),
            "charge_ratio": r(n["charge_to_payment_ratio"], 3),
        }
        for n in national
    ]

    states = rows(con, "select * from mart_state_year order by data_year, state")
    st: dict[str, Any] = {}
    for s in states:
        st.setdefault(s["state"], []).append(
            [
                s["data_year"],
                s["discharges"],
                r(s["payment_index"]),
                r(s["charge_index"]),
                r(s["charge_to_payment_ratio"]),
            ]
        )

    area = rows(con, "select * from mart_area_type_year order by data_year, area_type")
    areas = [
        {
            "year": a["data_year"],
            "area": a["area_type"],
            "hospitals": a["hospitals"],
            "discharges": a["discharges"],
            "payment_index": r(a["payment_index"]),
            "charge_index": r(a["charge_index"]),
            "charge_ratio": r(a["charge_to_payment_ratio"]),
        }
        for a in area
    ]

    drg_years = rows(con, "select * from mart_drg_year order by drg_code, data_year")
    drgs: dict[str, Any] = {}
    for d in drg_years:
        e = drgs.setdefault(d["drg_code"], {"code": d["drg_code"], "desc": d["drg_desc"], "years": []})
        e["years"].append(
            [
                d["data_year"],
                d["hospitals"],
                d["discharges"],
                r(d["avg_payment"], 0),
                r(d["avg_charges"], 0),
                r(d["payment_p10"], 0),
                r(d["payment_p50"], 0),
                r(d["payment_p90"], 0),
                r(d["charges_p10"], 0),
                r(d["charges_p50"], 0),
                r(d["charges_p90"], 0),
            ]
        )

    top = [
        x["drg_code"]
        for x in rows(
            con,
            """
        select drg_code from mart_drg_year where data_year = ? and hospitals >= ?
        order by discharges desc limit ?""",
            [latest, MIN_DRG_HOSPITALS, TOP_DRGS],
        )
    ]
    detail = {}
    for code in top:
        pts = con.execute(
            """
            select f.ccn, f.state, f.discharges, round(f.avg_total_payment), round(f.avg_covered_charges)
            from fct_provider_drg_year f where f.data_year = ? and f.drg_code = ? order by f.avg_total_payment""",
            [latest, code],
        ).fetchall()
        detail[code] = [list(p) for p in pts]

    hosp = con.execute(
        """
        select ccn, provider_name, city, state, area_type, discharges, drgs,
               round(payment_index, 3), round(charge_index, 3), round(charge_to_payment_ratio, 2)
        from mart_provider_year where data_year = ? order by discharges desc""",
        [latest],
    ).fetchall()
    hospitals = [list(h) for h in hosp]

    # findings: every sentence on the page and in the README is computed here
    spread = rows(
        con,
        """
        select drg_code, drg_desc, hospitals, payment_spread_90_10, charges_spread_90_10, charge_to_payment_ratio,
               payment_p10, payment_p90, charges_p10, charges_p90
        from mart_drg_year where data_year = ? and hospitals >= ? order by discharges desc limit 10""",
        [latest, MIN_DRG_HOSPITALS],
    )
    rankable = rows(
        con,
        """
        select provider_name, city, state, charge_index, payment_index, charge_to_payment_ratio, discharges
        from mart_provider_year where data_year = ? and rankable order by charge_to_payment_ratio desc""",
        [latest],
    )
    ratios = sorted(h["charge_to_payment_ratio"] for h in rankable)
    med = ratios[len(ratios) // 2] if ratios else None
    first = nat[0]
    last = nat[-1]
    findings = {
        "latest_year": latest,
        "first_year": first["year"],
        "national_latest": last,
        "per_discharge_growth": r(last["per_discharge"] / first["per_discharge"] - 1, 4)
        if first["per_discharge"]
        else None,
        "median_hospital_charge_ratio": r(med, 2),
        "highest_charge_ratio_hospitals": [
            {
                "name": h["provider_name"],
                "city": h["city"],
                "state": h["state"],
                "ratio": r(h["charge_to_payment_ratio"], 2),
                "discharges": h["discharges"],
            }
            for h in rankable[:5]
        ],
        "lowest_charge_ratio_hospitals": [
            {
                "name": h["provider_name"],
                "city": h["city"],
                "state": h["state"],
                "ratio": r(h["charge_to_payment_ratio"], 2),
                "discharges": h["discharges"],
            }
            for h in rankable[-5:][::-1]
        ],
        "top_drg_spreads": [{k: (r(v, 2) if isinstance(v, float) else v) for k, v in s.items()} for s in spread],
        "rankable_hospitals": len(rankable),
    }
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_year": latest,
        "years": [n["year"] for n in nat],
        "top_drgs": top,
        "source": "CMS Medicare Inpatient Hospitals - by Provider and Service",
    }
    files = {
        "meta.json": meta,
        "national.json": nat,
        "states.json": st,
        "areas.json": areas,
        "drgs.json": list(drgs.values()),
        "drg_hospitals.json": detail,
        "hospitals.json": {
            "columns": [
                "ccn",
                "name",
                "city",
                "state",
                "area",
                "discharges",
                "drgs",
                "payment_index",
                "charge_index",
                "charge_ratio",
            ],
            "rows": hospitals,
        },
        "findings.json": findings,
    }
    for name, doc in files.items():
        (out / name).write_text(json.dumps(doc, separators=(",", ":"), default=str), encoding="utf-8")
    con.close()
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, default=Path("build/medicare.duckdb"))
    p.add_argument("--out", type=Path, default=Path("site/data"))
    args = p.parse_args(argv)
    f = export(args.db, args.out)
    print(json.dumps({k: f[k] for k in ("latest_year", "median_hospital_charge_ratio", "rankable_hospitals")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
