-- States compared on a case-mix-adjusted basis (payment and charge indices; 1.00 = national average).
select
    data_year,
    state,
    count(distinct ccn)                                    as hospitals,
    sum(discharges)                                        as discharges,
    sum(total_payment)                                     as total_payment,
    sum(total_payment) / sum(expected_payment)             as payment_index,
    sum(total_covered_charges) / sum(expected_charges)     as charge_index,
    sum(total_covered_charges) / sum(total_payment)        as charge_to_payment_ratio
from {{ ref('fct_provider_drg_year') }}
group by data_year, state
