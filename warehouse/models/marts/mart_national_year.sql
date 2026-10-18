-- The national picture by year.
select
    data_year,
    count(distinct ccn)                                    as hospitals,
    count(distinct drg_code)                               as drgs,
    sum(discharges)                                        as discharges,
    sum(total_payment)                                     as total_payment,
    sum(total_medicare_payment)                            as total_medicare_payment,
    sum(total_medicare_payment) / sum(total_payment)       as medicare_share,
    sum(total_payment) / sum(discharges)                   as payment_per_discharge,
    sum(total_covered_charges) / sum(total_payment)        as charge_to_payment_ratio
from {{ ref('fct_provider_drg_year') }}
group by data_year
