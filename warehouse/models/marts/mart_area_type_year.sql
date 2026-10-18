-- Metropolitan vs micropolitan vs rural hospitals, case-mix adjusted.
select
    f.data_year,
    p.area_type,
    count(distinct f.ccn)                                  as hospitals,
    sum(f.discharges)                                      as discharges,
    sum(f.total_payment) / sum(f.expected_payment)         as payment_index,
    sum(f.total_covered_charges) / sum(f.expected_charges) as charge_index,
    sum(f.total_covered_charges) / sum(f.total_payment)    as charge_to_payment_ratio
from {{ ref('fct_provider_drg_year') }} f
join {{ ref('dim_provider') }} p using (ccn)
group by f.data_year, p.area_type
