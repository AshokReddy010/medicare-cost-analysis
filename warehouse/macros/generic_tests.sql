{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

{% test in_range(model, column_name, min=none, max=none) %}
select *
from {{ model }}
where {{ column_name }} is not null
  and (false
  {% if min is not none %} or {{ column_name }} < {{ min }} {% endif %}
  {% if max is not none %} or {{ column_name }} > {{ max }} {% endif %})
{% endtest %}

{% test not_above(model, column_name, other, tolerance=0) %}
select *
from {{ model }}
where {{ column_name }} > {{ other }} + {{ tolerance }}
{% endtest %}
