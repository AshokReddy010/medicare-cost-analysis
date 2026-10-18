"""Write the findings section of README.md from the published data, so the prose never drifts from the numbers.

python -m medicare.readme            (run after medicare.export; the refresh workflow does this)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

START, END = "<!-- FINDINGS:START -->", "<!-- FINDINGS:END -->"


def title(s: str) -> str:
    small = {"or", "and", "with", "without", "of", "in", "the"}
    keep = {"mcc": "MCC", "cc": "CC", "mv": "MV"}
    words = s.lower().split()
    return " ".join(keep.get(w, w if (i and w in small) else w.capitalize()) for i, w in enumerate(words))


def render(data: Path) -> str:
    f = json.loads((data / "findings.json").read_text())
    nat = json.loads((data / "national.json").read_text())
    states = json.loads((data / "states.json").read_text())
    y = f["latest_year"]
    last, first = nat[-1], nat[0]
    pre = next((r for r in nat if r["year"] == 2019), None)
    big = [(s, next(r for r in v if r[0] == y)) for s, v in states.items() if any(r[0] == y for r in v)]
    big = [(s, r) for s, r in big if r[1] >= 0.001 * last["discharges"]]  # leave out tiny state samples
    by_pay = sorted(big, key=lambda x: -x[1][2])
    by_ratio = sorted(big, key=lambda x: -x[1][4])
    top = f["top_drg_spreads"][0]
    hi = f["highest_charge_ratio_hospitals"][0]
    lines = [
        f"## What the data shows ({first['year']}–{y})",
        "",
        f"- **Hospitals bill about {last['charge_ratio']:.1f}× what they are paid.** In {y}, {last['hospitals']:,} hospitals "
        f"billed Medicare ${last['charge_ratio']:.2f} in covered charges for every $1 of payment, up from "
        f"${first['charge_ratio']:.2f} in {first['year']}. At the median hospital the ratio is "
        f"{f['median_hospital_charge_ratio']:.1f}×; the highest among hospitals with at least 100 discharges is "
        f"{hi['name']} ({hi['city']}, {hi['state']}) at {hi['ratio']:.1f}×.",
        f"- **Billing varies far more than payment.** For {title(top['drg_desc'])} (DRG {top['drg_code']}, the most "
        f"common stay), the 90th-percentile hospital bills {top['charges_spread_90_10']:.1f}× what the 10th-percentile one does "
        f"(${top['charges_p10']:,.0f} vs ${top['charges_p90']:,.0f}), but is paid only {top['payment_spread_90_10']:.1f}× as much "
        f"(${top['payment_p10']:,.0f} vs ${top['payment_p90']:,.0f}). The same pattern holds across the ten most common DRGs.",
        f"- **Where payment is highest, case mix aside:** {', '.join(f'{s} ({r[2]:.2f})' for s, r in by_pay[:4])} against "
        f"{', '.join(f'{s} ({r[2]:.2f})' for s, r in by_pay[-3:])} at the low end, mostly Medicare's own wage-index adjustment. "
        f"Billed-to-paid is highest in {', '.join(f'{s} ({r[4]:.1f}×)' for s, r in by_ratio[:3])}.",
    ]
    md = next((r for st, r in big if st == "MD"), None)
    if md:
        lines.append(
            f"- **Maryland sets its own rates.** Under its all-payer rate setting, hospitals' charges sit close to "
            f"payments: {md[4]:.2f}× in {y}."
        )
    if pre:
        lines.append(
            f"- **Fewer, costlier stays.** Medicare fee-for-service discharges fell from {pre['discharges'] / 1e6:.2f} million in "
            f"2019 to {last['discharges'] / 1e6:.2f} million in {y}, while payment per stay rose from ${pre['per_discharge']:,.0f} to "
            f"${last['per_discharge']:,.0f}. The volume never recovered after 2020, consistent with the shift of beneficiaries to "
            f"Medicare Advantage, which this data does not cover."
        )
    lines += ["", "_Generated from the published data by `medicare.readme`; refreshed with every data update._"]
    return "\n".join(lines)


def update(readme: Path, data: Path) -> None:
    text = readme.read_text(encoding="utf-8")
    block = f"{START}\n{render(data)}\n{END}"
    text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
    readme.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    update(Path("README.md"), Path("site/data"))
    sys.exit(0)
