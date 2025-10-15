---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';

# report

---

## <><code style={{color: '#b52ee6'}}>class</code></> ReportMessage


Message container for a report.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> report_code** (<code>int</code>) <text>&#8212;</text> integer report code, interpreted by the backend



<details>
<summary>View Source</summary>
```python
@register_data
class ReportMessage(Datatype):
    """Message container for a report.    
    
    Attributes:
        report_code (int): integer report code, interpreted by the backend    
    """
    report_code: int

```
</details>


---
