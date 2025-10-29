---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# registry_completions

---

## <><code class="docs-func">func</code></> ensure_registry_initialized

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def ensure_registry_initialized() -> None:
    global _INITIALIZED, _REGISTRY_COMPLETIONS, _INLINE_DATA_COMPLETIONS
    if _INITIALIZED:
        return
    try:
        summaries = loader.load_all()
        loader.print_report(summaries)
    except Exception:  # pragma: no cover
        logger.exception("Failed to preload SDK registry for completions")
    _REGISTRY_COMPLETIONS, _INLINE_DATA_COMPLETIONS = _build_registry_lookup()
    _INITIALIZED = True

```
</details>

---
## <><code class="docs-func">func</code></> registry_items_for_section

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def registry_items_for_section(section: Optional[str], pfx: str) -> List[CompletionItem]:
    ensure_registry_initialized()
    if section not in (_REGISTRY_COMPLETIONS or {}):
        return []
    p = pfx.lower()
    items: List[CompletionItem] = []
    for entry in _REGISTRY_COMPLETIONS.get(section, []):
        if not p or p in entry.label.lower():
            items.append(entry.to_item())
    return items

```
</details>

---
## <><code class="docs-func">func</code></> inline_data_items

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def inline_data_items(pfx: str) -> List[CompletionItem]:
    ensure_registry_initialized()
    if not _INLINE_DATA_COMPLETIONS:
        return []
    p = pfx.lower()
    items: List[CompletionItem] = []
    for entry in _INLINE_DATA_COMPLETIONS:
        if not p or p in entry.label.lower():
            items.append(entry.to_item())
    return items

```
</details>

---
## <><code class="docs-class">class</code></> RegistryCompletion



### <><code class="docs-method">method</code></> to_item

_Call Type: normal_


<details>
<summary>View Source</summary>
```python
@dataclass
class RegistryCompletion:
    label: str
    insert_text: str
    detail: str
    documentation: Optional[str]
    sort_text: str
    kind: CompletionItemKind
    filter_text: Optional[str] = None

    def to_item(self) -> CompletionItem:
        doc = None
        if self.documentation:
            doc = MarkupContent(kind=MarkupKind.Markdown, value=self.documentation)
        return CompletionItem(
            label=self.label,
            kind=self.kind,
            detail=self.detail,
            insert_text=self.insert_text,
            insert_text_format=INSERT_TEXT_FORMAT_SNIPPET,
            documentation=doc,
            filter_text=self.filter_text or self.label,
            sort_text=self.sort_text,
        )

```
</details>


---
