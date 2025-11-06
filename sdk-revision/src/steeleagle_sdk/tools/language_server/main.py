from __future__ import annotations

import logging
from typing import List, Optional

from pygls.server import LanguageServer
from pygls.workspace import Document
from lsprotocol.types import (
    INITIALIZE,
    TEXT_DOCUMENT_COMPLETION,
    InitializeResult,
    CompletionParams,
    CompletionItem,
    CompletionItemKind,
    TextDocumentSyncKind,
    CompletionOptions,
    CompletionList,
    ServerCapabilities,
    TextDocumentSyncOptions,
)

from . import registry_completions as reg

logging.basicConfig(
    filename="./steeleagle_lsp.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SIMPLE_KEYWORDS = ["->", "Start", "During", "done", "Data", "Actions", "Events", "Mission"]

SECTION_SNIPPETS = [
    ("Data:", "Data:\n    ${1}"),
    ("Actions:", "Actions:\n    ${1}"),
    ("Events:", "Events:\n    ${1}"),
    ("Mission:", "Mission:\n    Start ${1:ActionId}"),
    ("During", "During ${1:ActionId}:\n    ${2:EventId} -> ${3:NextActionId}"),
    ("done ->", "done -> ${1:NextActionId}"),
]


def get_line_prefix(doc: Document, line: int, ch: int) -> str:
    lines = doc.source.splitlines()
    return lines[line][:ch] if 0 <= line < len(lines) else ""


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


def is_value_position(line_prefix: str, ident: str) -> bool:
    for sep in ("=", ":"):
        idx = line_prefix.rfind(sep)
        if idx == -1:
            continue
        suffix = line_prefix[idx + 1 :]
        if suffix.strip() == ident:
            return True
    return False


def ident_prefix(s: str) -> str:
    i = len(s)
    while i > 0 and (s[i - 1].isalnum() or s[i - 1] in ("_", "-")):
        i -= 1
    return s[i:]


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


srv = LanguageServer(name="steeleagle-dsl-lsp", version="1.0.0")


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


if __name__ == "__main__":
    srv.start_io()
