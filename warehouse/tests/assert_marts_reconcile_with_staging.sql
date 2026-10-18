-- Every discharge and every payment dollar in staging must reach the marts: nothing dropped by a join.
with s as (select data_year, sum(discharges) d, sum(total_payment) p from {{ ref('stg_inpatient') }} group by 1),
     n as (select data_year, discharges d, total_payment p from {{ ref('mart_national_year') }}),
     st as (select data_year, sum(discharges) d, sum(total_payment) p from {{ ref('mart_state_year') }} group by 1),
     pr as (select data_year, sum(discharges) d from {{ ref('mart_provider_year') }} group by 1)
select s.data_year
from s join n using (data_year) join st using (data_year) join pr using (data_year)
where s.d <> n.d or s.d <> st.d or s.d <> pr.d or abs(s.p - n.p) > 1 or abs(s.p - st.p) > 1
