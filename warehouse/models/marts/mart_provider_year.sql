-- Each hospital's yearly profile. The indices are case-mix adjusted: actual dollars divided by what the
-- national average would have been for the same DRGs and volumes (1.00 = national average).
select
    f.data_year,
    f.ccn,
    p.provider_name,
    p.city,
    p.state,
    p.area_type,
    count(*)                                              as drgs,
    sum(f.discharges)                                     as discharges,
    sum(f.total_payment)                                  as total_payment,
    sum(f.total_covered_charges)                          as total_charges,
    sum(f.total_payment) / sum(f.expected_payment)        as payment_index,
    sum(f.total_covered_charges) / sum(f.expected_charges) as charge_index,
    sum(f.total_covered_charges) / sum(f.total_payment)   as charge_to_payment_ratio,
    sum(f.discharges) >= {{ var('min_hospital_discharges') }} as rankable
from {{ ref('fct_provider_drg_year') }} f
join {{ ref('dim_provider') }} p using (ccn)
group by f.data_year, f.ccn, p.provider_name, p.city, p.state, p.area_type
