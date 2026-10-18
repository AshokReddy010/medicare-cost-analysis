-- The analysis grain: one hospital, one DRG, one year, with case-mix-free indices.
select
    data_year, ccn, drg_code, state, discharges,
    avg_total_payment, avg_medicare_payment, avg_covered_charges,
    total_payment, total_medicare_payment, total_covered_charges,
    payment_index, charge_index, charge_to_payment_ratio, expected_payment, expected_charges
from {{ ref('int_provider_drg_indexed') }}
