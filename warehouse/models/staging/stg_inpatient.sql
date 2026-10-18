-- One row per hospital, DRG and year, typed, with the per-row totals the averages imply.
select
    cast(data_year as integer)                          as data_year,
    ccn,
    provider_name,
    city,
    state,
    zip5,
    cast(ruca as double)                                as ruca,
    ruca_desc,
    drg_code,
    drg_desc,
    cast(discharges as integer)                         as discharges,
    cast(avg_covered_charges as double)                 as avg_covered_charges,
    cast(avg_total_payment as double)                   as avg_total_payment,
    cast(avg_medicare_payment as double)                as avg_medicare_payment,
    discharges * avg_covered_charges                    as total_covered_charges,
    discharges * avg_total_payment                      as total_payment,
    discharges * avg_medicare_payment                   as total_medicare_payment
from {{ source('cms', 'inpatient') }}
where discharges > 0 and avg_total_payment > 0
