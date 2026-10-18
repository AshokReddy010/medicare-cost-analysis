# Same diagnosis, different bill

[![ci](https://github.com/AshokReddy010/medicare-cost-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/AshokReddy010/medicare-cost-analysis/actions/workflows/ci.yml)
[![refresh](https://github.com/AshokReddy010/medicare-cost-analysis/actions/workflows/refresh.yml/badge.svg)](https://github.com/AshokReddy010/medicare-cost-analysis/actions/workflows/refresh.yml)

**▶ [Interactive dashboard](https://ashokreddy010.github.io/medicare-cost-analysis/)** · [dbt docs and lineage](https://ashokreddy010.github.io/medicare-cost-analysis/dbt-docs.html)

What do US hospitals bill Medicare for the same inpatient stay, and what are they actually paid? This project models every public release of CMS's *Medicare Inpatient Hospitals – by Provider and Service* (one row per hospital per diagnosis-related group per year, 2013 onward) into a tested dbt warehouse in DuckDB, and publishes an explorer of the results.

<!-- FINDINGS:START -->
## What the data shows (2013–2024)

- **Hospitals bill about 5.0× what they are paid.** In 2024, 2,906 hospitals billed Medicare $5.03 in covered charges for every $1 of payment, up from $3.85 in 2013. At the median hospital the ratio is 4.2×; the highest among hospitals with at least 100 discharges is Capital Health Medical Center - Hopewell (Pennington, NJ) at 22.7×.
- **Billing varies far more than payment.** For Septicemia or Severe Sepsis without MV >96 Hours with MCC (DRG 871, the most common stay), the 90th-percentile hospital bills 4.4× what the 10th-percentile one does ($32,161 vs $140,999), but is paid only 1.8× as much ($13,356 vs $23,576). The same pattern holds across the ten most common DRGs.
- **Where payment is highest, case mix aside:** MD (1.40), NY (1.30), AK (1.28), CA (1.28) against VT (0.79), MS (0.76), AR (0.76) at the low end, mostly Medicare's own wage-index adjustment. Billed-to-paid is highest in NV (9.1×), CO (7.4×), FL (7.1×).
- **Maryland sets its own rates.** Under its all-payer rate setting, hospitals' charges sit close to payments: 1.11× in 2024.
- **Fewer, costlier stays.** Medicare fee-for-service discharges fell from 6.96 million in 2019 to 4.95 million in 2024, while payment per stay rose from $14,623 to $18,360. The volume never recovered after 2020, consistent with the shift of beneficiaries to Medicare Advantage, which this data does not cover.

_Generated from the published data by `medicare.readme`; refreshed with every data update._
<!-- FINDINGS:END -->

## Questions it answers

- For a given diagnosis group, how far apart are hospitals on what they **bill** and on what they are **paid**?
- Which states and which hospitals are expensive once you compare like for like (same diagnoses, same volumes)?
- How do metropolitan, micropolitan and rural hospitals compare?
- How did volumes and payment per stay move across a decade, including the 2020 collapse in admissions?

## Pipeline

```
data.gov catalog ──> medicare.fetch ──> data/raw/inpatient_<year>.parquet ──> dbt (DuckDB) ──> medicare.export ──> site/data/*.json ──> dashboard
                     discover files,      one normalised file per year        staging → intermediate → marts      compact JSON + findings
                     map renamed columns
```

**Ingestion.** File URLs come from the data.gov CKAN API, so a new data year is picked up automatically (a pinned list is the fallback). CMS renamed columns between releases (`Rndrng_CCN` vs `Rndrng_Prvdr_CCN`, letter case), so columns are matched by alias, and a release with a column the loader cannot place fails the job instead of loading wrong.

**Models** (`warehouse/`):

| Layer | Model | Grain / purpose |
|---|---|---|
| staging | `stg_inpatient` | hospital × DRG × year, typed, with implied totals (average × discharges) |
| intermediate | `int_drg_year_benchmarks` | the national yardstick per DRG-year: average paid, Medicare paid, billed |
| | `int_provider_drg_indexed` | each row relative to its yardstick |
| marts | `dim_provider`, `dim_drg` | latest names, locations, RUCA area type; DRG descriptions and years present |
| | `fct_provider_drg_year` | the analysis grain with payment and charge indices |
| | `mart_drg_year` | hospital-level spread per DRG-year: p10/p50/p90 of paid and billed |
| | `mart_provider_year`, `mart_state_year`, `mart_area_type_year`, `mart_national_year` | case-mix-adjusted comparisons |

**Case-mix adjustment.** A hospital that does many joint replacements is not expensive just because joint replacements are. For each DRG and year the national average per discharge is the yardstick; a hospital's (or state's) index is its actual dollars divided by the yardstick dollars for its own DRGs and volumes. By construction the national index is exactly 1.00, which is itself a test.

**Tests.** Unique keys at every grain, not-null and accepted values, relationships from the fact to both dimensions, value ranges, Medicare payment never above total payment (warn), p10 ≤ p90, a reconciliation test that every discharge and payment dollar in staging reaches every mart, and the national-index identity. Python tests cover the column-alias normaliser, schema-drift failures, catalog discovery and fallback, incremental downloads, and a full dbt build plus export on a synthetic fixture release (CI runs this on every push; the real data is built by the monthly `refresh` workflow).

## Reading the numbers carefully

- **Billed is not owed.** Covered charges are list prices. Medicare pays a fixed amount per DRG, adjusted for local wages, teaching status, share of low-income patients, and outlier cases. The billed-to-paid ratio measures chargemaster markup; it is what uninsured patients may be quoted, not what Medicare or patients pay.
- **Payment differences are mostly policy.** Variation in what hospitals are *paid* for the same DRG largely reflects Medicare's own adjustments (wage index, teaching, disproportionate share), not hospitals choosing prices.
- **Coverage.** Medicare fee-for-service only (no Medicare Advantage, no private insurance); cells under 11 discharges are suppressed by CMS; DRG definitions are revised over the years, so long trends for one DRG should be read with that in mind.

## Run it

```bash
pip install -e ".[dev]"
python -m medicare.fetch --years 2023 2024        # or no flag for every year (~12 files)
cd warehouse && dbt build --profiles-dir . && cd ..
python -m medicare.export
python -m http.server -d site                     # open http://localhost:8000/?base=data/
```

Without network access, `python -m medicare.fixtures` writes a small synthetic release in the same layout.

## License

Code: MIT. Data: CMS, public domain.
