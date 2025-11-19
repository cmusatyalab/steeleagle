---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# main

---

## <><code class="docs-func">func</code></> get_line_prefix

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def get_line_prefix(doc: Document, line: int, ch: int) -> str:
    lines = doc.source.splitlines()
    return lines[line][:ch] if 0 <= line < len(lines) else ""

```
</details>

---
## <><code class="docs-func">func</code></> detect_section

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def detect_section(doc: Document, line: int) -> Optional[str]:
    lines = doc.source.splitlines()
    i = min(line, len(lines) - 1)
    while i >= 0:
        stripped = lines[i].strip()
        if stripped.startswith("Mission:"):
            return "mission"
        if stripped.startswith("Events:"):
            return "events"
        if stripped.startswith("Actions:"):
            return "actions"
        if stripped.startswith("Data:"):
            return "data"
        i -= 1
    return None

```
</details>

---
## <><code class="docs-func">func</code></> is_value_position

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def is_value_position(line_prefix: str, ident: str) -> bool:
    for sep in ("=", ":"):
        idx = line_prefix.rfind(sep)
        if idx == -1:
            continue
        suffix = line_prefix[idx + 1 :]
        if suffix.strip() == ident:
            return True
    return False

```
</details>

---
## <><code class="docs-func">func</code></> ident_prefix

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def ident_prefix(s: str) -> str:
    i = len(s)
    while i > 0 and (s[i - 1].isalnum() or s[i - 1] in ("_", "-")):
        i -= 1
    return s[i:]

```
</details>

---
## <><code class="docs-func">func</code></> items_section_snippets

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def items_section_snippets(pfx: str) -> List[CompletionItem]:
    p = pfx.lower()
    items: List[CompletionItem] = []
    for label, snippet in SECTION_SNIPPETS:
        if p in label.lower():
            items.append(
                CompletionItem(
                    label=label,
                    kind=CompletionItemKind.Keyword,
                    detail="snippet",
                    insert_text=snippet,
                    insert_text_format=reg.INSERT_TEXT_FORMAT_SNIPPET,
                    sort_text=f"80_{label}",
                )
            )
    return items

```
</details>

---
## <><code class="docs-func">func</code></> items_simple_keywords

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def items_simple_keywords(pfx: str) -> List[CompletionItem]:
    p = pfx.lower()
    return [
        CompletionItem(
            label=kw,
            kind=CompletionItemKind.Keyword,
            detail="keyword",
            insert_text=kw,
            sort_text=f"90_{kw}",
        )
        for kw in SIMPLE_KEYWORDS
        if p in kw.lower()
    ]

```
</details>

---
## <><code class="docs-func">func</code></> on_init

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
@srv.feature(INITIALIZE)
def on_init(ls, _):
    logger.info("INITIALIZE request received")
    reg.ensure_registry_initialized()
    return InitializeResult(
        capabilities=ServerCapabilities(
            text_document_sync=TextDocumentSyncOptions(open_close=True, change=TextDocumentSyncKind.Incremental),
            completion_provider=CompletionOptions(trigger_characters=[":", ">", "-", " ", "_", "(", ")", ",", "="]),
        )
    )

```
</details>

---
## <><code class="docs-func">func</code></> on_complete

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
@srv.feature(TEXT_DOCUMENT_COMPLETION)
def on_complete(ls, params: CompletionParams):
    logger.info(
        "COMPLETION request for %s at line %d, char %d",
        params.text_document.uri,
        params.position.line,
        params.position.character,
    )
    try:
        doc = ls.workspace.get_document(params.text_document.uri)
        line_pref = get_line_prefix(doc, params.position.line, params.position.character)
        pfx = ident_prefix(line_pref)
        section = detect_section(doc, params.position.line)
        value_ctx = is_value_position(line_pref, pfx)

        items: List[CompletionItem] = []
        items += reg.registry_items_for_section(section, pfx)
        if value_ctx:
            items += reg.inline_data_items(pfx)
        items += items_section_snippets(pfx)
        items += items_simple_keywords(pfx)

        logger.info("Returning %d completion items", len(items))
        return CompletionList(is_incomplete=False, items=items)
    except Exception as exc:
        logger.exception("Error in completion handler: %s", exc)
        return CompletionList(is_incomplete=False, items=[])

```
</details>

---
