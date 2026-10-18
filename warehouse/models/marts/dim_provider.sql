-- Hospitals (by CMS Certification Number) with their most recent name and location.
with latest as (
    select *, row_number() over (partition by ccn order by data_year desc, discharges desc) as rk
    from {{ ref('stg_inpatient') }}
)
select
    l.ccn,
    l.provider_name,
    l.city,
    l.state,
    l.zip5,
    l.ruca,
    {{ ruca_group('l.ruca') }}                 as area_type,
    y.first_year,
    y.last_year
from latest l
join (select ccn, min(data_year) as first_year, max(data_year) as last_year
      from {{ ref('stg_inpatient') }} group by ccn) y using (ccn)
where l.rk = 1
