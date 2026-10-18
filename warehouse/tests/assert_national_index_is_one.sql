-- By construction the discharge-weighted payment index across all hospitals is 1.00 in every year.
select data_year, sum(total_payment) / sum(expected_payment) as idx
from {{ ref('fct_provider_drg_year') }}
group by data_year
having abs(sum(total_payment) / sum(expected_payment) - 1) > 1e-9
