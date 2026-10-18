-- Diagnosis-related groups with their most recent description and the years they appear in.
with ranked as (
    select drg_code, drg_desc, data_year,
           row_number() over (partition by drg_code order by data_year desc) as rk
    from {{ ref('stg_inpatient') }}
    group by drg_code, drg_desc, data_year
)
select
    drg_code,
    max(case when rk = 1 then drg_desc end)   as drg_desc,
    min(data_year)                             as first_year,
    max(data_year)                             as last_year,
    count(distinct data_year)                  as years_present
from ranked
group by drg_code
