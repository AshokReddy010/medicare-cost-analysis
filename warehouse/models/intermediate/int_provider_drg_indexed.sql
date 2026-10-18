-- Each hospital-DRG-year row expressed relative to the national yardstick for that DRG and year.
select
    s.*,
    s.avg_total_payment / b.national_avg_payment     as payment_index,
    s.avg_covered_charges / b.national_avg_charges   as charge_index,
    s.avg_covered_charges / s.avg_total_payment      as charge_to_payment_ratio,
    b.national_avg_payment * s.discharges            as expected_payment,
    b.national_avg_charges * s.discharges            as expected_charges
from {{ ref('stg_inpatient') }} s
join {{ ref('int_drg_year_benchmarks') }} b using (data_year, drg_code)
