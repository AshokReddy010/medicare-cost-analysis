-- How much the price of the same DRG varies between hospitals, year by year.
-- Spreads use hospital-level averages (unweighted quantiles): "what does it cost at the 10th vs the
-- 90th percentile hospital", which is the question a patient or a payer asks.
select
    f.data_year,
    f.drg_code,
    d.drg_desc,
    count(*)                                                        as hospitals,
    sum(f.discharges)                                               as discharges,
    sum(f.total_payment)                                            as total_payment,
    {{ wavg('f.avg_total_payment') }}                               as avg_payment,
    {{ wavg('f.avg_covered_charges') }}                             as avg_charges,
    sum(f.total_covered_charges) / sum(f.total_payment)             as charge_to_payment_ratio,
    quantile_cont(f.avg_total_payment, 0.10)                        as payment_p10,
    quantile_cont(f.avg_total_payment, 0.50)                        as payment_p50,
    quantile_cont(f.avg_total_payment, 0.90)                        as payment_p90,
    quantile_cont(f.avg_covered_charges, 0.10)                      as charges_p10,
    quantile_cont(f.avg_covered_charges, 0.50)                      as charges_p50,
    quantile_cont(f.avg_covered_charges, 0.90)                      as charges_p90,
    quantile_cont(f.avg_total_payment, 0.90) / quantile_cont(f.avg_total_payment, 0.10)     as payment_spread_90_10,
    quantile_cont(f.avg_covered_charges, 0.90) / quantile_cont(f.avg_covered_charges, 0.10) as charges_spread_90_10
from {{ ref('fct_provider_drg_year') }} f
join {{ ref('dim_drg') }} d using (drg_code)
group by f.data_year, f.drg_code, d.drg_desc
