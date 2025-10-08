# {{ package }}

{{ docstring }}

{% if functions | length > 0%}
## Functions
{% for function in functions %}
### `{{ function.name }}`
```python
{{ function.signature }}
```
{{ function.docstring }}
{% endif %}

---
{% endfor %}
{% endif %}
{% if classes | length > 0%}
## Classes

{% for class in classes %}
### `{{ class.name }}`
{% if class.inheritance %}*Inherits from: {{ class.inheritance }}*{% endif %}

{{ class.comment }}

{% if class.functions %}
#### Methods
{% for function in class.functions %}
##### `{{ function.name }}`
{% if function.inheritance %}*Inherited from {{ function.inheritance }}*{% endif %}

{{ function.comment }}
{% endif %}
{% endfor %}
{% endif %}

---
{% endfor %}
{% endif %}
