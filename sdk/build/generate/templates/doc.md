---
toc_max_heading_level: 2
---
# {{ name }}

{% if comment %}
{{ comment }}

{% endif %}
---

{% if attributes | length > 0 %}
{% for attribute in attributes %}
{% if not attribute.name.startswith('_') %}
## {% raw %}<><code style={{color: '#e0a910'}}>attr</code></>{% endraw %} {{ attribute.name }}

{% if attribute.type %}
_{{ attribute.type }}_
{% endif %}

{% if attribute.comment %}
{{ attribute.comment }}
{% endif %}

---
{% endif %}
{% endfor %}
{% endif %}
{% if functions | length > 0 %}
{% for function in functions %}
{% if not function.name.startswith('_') %}
## {% raw %}<><code style={{color: '#13a6cf'}}>func</code></>{% endraw %} {{ function.name }}
{% if function.comment %}

{{ function.comment}}
{% endif %}
{% if function.args | length > 0%}

### Arguments
{% for arg in function.args %}
{% if not arg.name.startswith('_') %}
**{% raw %}<><code style={{color: '#db2146'}}>arg</code></>{% endraw %} {{ arg.name }}**{% if arg.type %} ({{ arg.type }}){% endif %}
{% if arg.comment %} <text>&#8212;</text> {{ arg.comment }}{% endif %}


{% endif %}
{% endfor %}
{% endif %}
{% if function.ret %}

### Returns

{% if function.ret.type %}{{ function.ret.type }}{% endif %}
{% if function.ret.comment %} <text>&#8212;</text> {{ function.ret.comment }}{% endif %}

{% endif %}

---
{% endif %}
{% endfor %}
{% endif %}
{% if classes | length > 0%}
{% for class in classes %}
{% if not class.name.startswith('_') %}
## {% raw %}<><code style={{color: '#b52ee6'}}>class</code></>{% endraw %} {{ class.name }}

{% if class.inheritance %}
*Inherits from: {{ class.inheritance }}*
{% endif %}
{% if class.comment %}

{{ class.comment }}
{% endif %}
{% if class.attributes | length > 0%}
#### Attributes
{% for attr in class.attributes %}
{% if not attr.name.startswith('_') %}
**{% raw %}<><code style={{color: '#e0a910'}}>attr</code></>{% endraw %} {{ attr.name }}**{% if attr.type %} ({{ attr.type }}){% endif %}
{% if attr.comment %} <text>&#8212;</text> {{ attr.comment }}{% endif %}


{% endif %}
{% endfor %}
{% endif %}

{% if class.functions %}

{% for function in class.functions %}
{% if not function.name.startswith('_') %}
### {% raw %}<><code style={{color: '#10c45b'}}>method</code></>{% endraw %} {{ function.name }}

{% if function.inheritance %}
*Inherited from {{ function.inheritance }}*
{% endif %}
{% if function.comment %}

{{ function.comment }}
{% endif %}
{% if function.args | length > 0%}

#### Arguments
{% for arg in function.args %}
{% if not arg.name.startswith('_') %}
**{% raw %}<><code style={{color: '#db2146'}}>arg</code></>{% endraw %} {{ arg.name }}**{% if arg.type %} ({{ arg.type }}){% endif %}
{% if arg.comment %} <text>&#8212;</text> {{ arg.comment }}{% endif %}


{% endif %}
{% endfor %}
{% endif %}
{% if function.ret %}

#### Returns

{% if function.ret.type %}{{ function.ret.type }}{% endif %}
{% if function.ret.comment %} <text>&#8212;</text> {{ function.ret.comment }}{% endif %}

{% endif %}
{% endif %}
{% endfor %}
{% endif %}

---
{% endif %}
{% endfor %}
{% endif %}
