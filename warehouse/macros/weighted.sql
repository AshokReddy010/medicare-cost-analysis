{# Discharge-weighted mean of a per-row average: the true average per discharge across rows. #}
{% macro wavg(value, weight='discharges') -%}
    sum({{ value }} * {{ weight }}) / nullif(sum({{ weight }}), 0)
{%- endmacro %}

{# RUCA codes 1-3 are metropolitan, 4-6 micropolitan, 7-10 small town and rural (USDA ERS). #}
{% macro ruca_group(ruca) -%}
    case
        when {{ ruca }} is null then 'Unknown'
        when floor({{ ruca }}) between 1 and 3 then 'Metropolitan'
        when floor({{ ruca }}) between 4 and 6 then 'Micropolitan'
        else 'Small town and rural'
    end
{%- endmacro %}
