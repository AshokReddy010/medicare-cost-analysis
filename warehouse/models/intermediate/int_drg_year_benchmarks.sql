-- The national yardstick for each DRG in each year: what an average discharge is paid and charged.
-- Comparing a hospital with this yardstick DRG by DRG removes the effect of case mix (a hospital that
-- does many joint replacements is not "expensive" just because joint replacements are).
select
    data_year,
    drg_code,
    count(*)                                   as hospitals,
    sum(discharges)                            as discharges,
    {{ wavg('avg_total_payment') }}            as national_avg_payment,
    {{ wavg('avg_medicare_payment') }}         as national_avg_medicare_payment,
    {{ wavg('avg_covered_charges') }}          as national_avg_charges
from {{ ref('stg_inpatient') }}
group by data_year, drg_code
