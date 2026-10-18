"""A small synthetic release in CMS's raw column layout, for tests and CI (the real files are fetched in Actions).

It mimics the real structure: hospitals in several states with different wage levels, DRGs with very
different base payments, payments set close to Medicare's formula, and charges at hospital-specific markups.
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from .fetch import normalise

STATES = {"CA": ("06", 1.35), "NY": ("36", 1.3), "TX": ("48", 0.95), "AL": ("01", 0.78), "IL": ("17", 1.02)}
DRGS = [
    ("470", "MAJOR HIP AND KNEE JOINT REPLACEMENT OR REATTACHMENT OF LOWER EXTREMITY WITHOUT MCC", 13500),
    ("871", "SEPTICEMIA OR SEVERE SEPSIS WITHOUT MV >96 HOURS WITH MCC", 15800),
    ("291", "HEART FAILURE AND SHOCK WITH MCC", 10400),
    ("392", "ESOPHAGITIS, GASTROENTERITIS AND MISC DIGESTIVE DISORDERS WITHOUT MCC", 5600),
    ("190", "CHRONIC OBSTRUCTIVE PULMONARY DISEASE WITH MCC", 8700),
    ("065", "INTRACRANIAL HEMORRHAGE OR CEREBRAL INFARCTION WITH CC OR TPA IN 24 HRS", 7900),
    ("247", "PERCUTANEOUS CARDIOVASCULAR PROCEDURES WITH DRUG-ELUTING STENT WITHOUT MCC", 15100),
    ("683", "RENAL FAILURE WITH CC", 7100),
]


def raw_release(year: int, hospitals: int = 40, seed: int = 7) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for h in range(hospitals):
        st = rng.choice(list(STATES))
        fips, wage = STATES[st]
        markup = rng.uniform(2.0, 7.5)
        teaching = rng.random() < 0.25
        ruca = rng.choice([1, 1, 1, 2, 4, 7, 10])
        for code, desc, base in DRGS:
            if rng.random() < 0.15:
                continue  # not every hospital treats every DRG (and small cells are suppressed)
            dis = max(11, int(rng.lognormvariate(3.2, 0.8)))
            year_factor = 1 + 0.025 * (year - 2019)
            pay = base * wage * year_factor * (1.12 if teaching else 1.0) * rng.uniform(0.93, 1.08)
            rows.append(
                {
                    "Rndrng_Prvdr_CCN": f"{h * 37 + 10001:06d}",
                    "Rndrng_Prvdr_Org_Name": f"Hospital {h} Medical Center",
                    "Rndrng_Prvdr_St": f"{h + 1} Main St",
                    "Rndrng_Prvdr_City": f"City{h % 9}",
                    "Rndrng_Prvdr_State_Abrvtn": st,
                    "Rndrng_Prvdr_State_FIPS": fips,
                    "Rndrng_Prvdr_Zip5": f"{rng.randint(1000, 99999):05d}",
                    "Rndrng_Prvdr_RUCA": str(ruca),
                    "Rndrng_Prvdr_RUCA_Desc": "Metropolitan area core" if ruca == 1 else "Other",
                    "DRG_Cd": code,
                    "DRG_Desc": desc,
                    "Tot_Dschrgs": str(dis),
                    "Avg_Submtd_Cvrd_Chrg": f"{pay * markup:.2f}",
                    "Avg_Tot_Pymt_Amt": f"{pay:.2f}",
                    "Avg_Mdcr_Pymt_Amt": f"{pay * rng.uniform(0.82, 0.9):.2f}",
                }
            )
    return pd.DataFrame(rows)


def write_fixture(out_dir: Path, years: tuple[int, ...] = (2022, 2023, 2024)) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for y in years:
        raw = raw_release(y, seed=11)
        if y == years[0]:  # an older release used the shorter CCN column name
            raw = raw.rename(columns={"Rndrng_Prvdr_CCN": "Rndrng_CCN"})
        p = out_dir / f"inpatient_{y}.parquet"
        normalise(raw, y).to_parquet(p, index=False)
        paths.append(p)
    return paths


if __name__ == "__main__":
    print(write_fixture(Path("data/raw")))
