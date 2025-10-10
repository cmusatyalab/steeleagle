from __future__ import annotations
from pathlib import Path
from importlib import resources
from typing import List, Tuple, Optional
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
    MarkupContent,
    MarkupKind,
    CompletionList,
    ServerCapabilities,
    TextDocumentSyncOptions,
    InsertTextFormat,
)
from lark import Lark, Tree, Token, Visitor
import logging
import re

# Configure logging to file for debugging
logging.basicConfig(
    filename='./steeleagle_lsp.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Keywords & Snippets ----------------------------------------------------
# Keep simple lowercase keywords that are valid in-line
SIMPLE_KEYWORDS = [
    "->", "Start"
]

# Section headers and common scaffolds that match the grammar's casing
SECTION_SNIPPETS: List[Tuple[str, str]] = [
    ("Data:", "Data:\n    ${1}"),
    ("Actions:", "Actions:\n    ${1}"),
    ("Mission:", "Mission:\n    Start ${1:ActionId}"),
    ("During", "During ${1:ActionId}:\n    done -> ${2:NextActionId}"),
    ("done ->", "done -> ${1:NextActionId}"),
]

BUILTIN_ACTIONS: List[Tuple[str,str,str]] = [
    ("TakeOff","action","Arm and ascend"),
    ("SetVelocity","action","Set velocity (m/s)"),
    ("SetGlobalPosition","action","Go to GPS point"),
]

# --- Parser & Symbols -------------------------------------------------------
class Parser:
    def __init__(self) -> None:
        try:
            logger.info("Initializing Parser")
            grammar_file = resources.files("steeleagle_sdk.dsl.grammar") / "dronedsl.lark"
            logger.info(f"Grammar file path: {grammar_file}")
            with resources.as_file(grammar_file) as g:
                logger.info(f"Resolved grammar file: {g}")
                self._p = Lark.open(
                    str(g), parser="lalr", keep_all_tokens=True,
                    propagate_positions=True, maybe_placeholders=True
                )
            logger.info("Parser initialized successfully")
        except Exception as e:
            logger.exception(f"Failed to initialize Parser: {e}")
            raise

    def parse(self, text: str) -> Tree:
        try:
            logger.debug(f"Parsing text of length {len(text)}")
            result = self._p.parse(text)
            logger.debug("Parse successful")
            return result
        except Exception as e:
            logger.debug(f"Parse failed: {e}")
            raise

class Symbols:
    def __init__(self) -> None:
        self.actions: List[str] = []
        self.events: List[str] = []
        self.data: List[str] = []

class SymbolCollector(Visitor):
    @staticmethod
    def _second_name(tree: Tree) -> str | None:
        names = [str(ch) for ch in tree.children if isinstance(ch, Token) and ch.type == "NAME"]
        return names[1] if len(names) >= 2 else None

    def __init__(self, syms):
        self.syms = syms

    # --- match exact rule names from your grammar ---
    def datum_decl(self, tree: Tree) -> None:
        n = self._second_name(tree)
        if n:
            self.syms.data.append(n)

    def action_decl(self, tree: Tree) -> None:
        n = self._second_name(tree)
        if n:
            self.syms.actions.append(n)

    def event_decl(self, tree: Tree) -> None:
        n = self._second_name(tree)
        if n:
            self.syms.events.append(n)
            
def build_symbols(tree: Optional[Tree]) -> Symbols:
    syms = Symbols()
    if tree:
        try:
            SymbolCollector(syms).visit(tree)
        except Exception:
            pass
    # de-dupe
    syms.actions = list(dict.fromkeys(syms.actions))
    syms.events  = list(dict.fromkeys(syms.events))
    syms.data    = list(dict.fromkeys(syms.data))
    return syms

# Cache last-good symbols so transient parse errors don't nuke completions
LAST_GOOD_SYMS: Optional[Symbols] = None

def parse_with_cache(parser: Parser, text: str) -> Optional[Tree]:
    global LAST_GOOD_SYMS
    try:
        tree = parser.parse(text)
        LAST_GOOD_SYMS = build_symbols(tree)
        return tree
    except Exception:
        # On failure, keep tree as None but leave LAST_GOOD_SYMS as previous
        return None

# --- Utilities --------------------------------------------------------------
def get_line_prefix(doc: Document, line: int, ch: int) -> str:
    lines = doc.source.splitlines()
    return lines[line][:ch] if 0 <= line < len(lines) else ""

def get_line_text(doc: Document, line: int) -> str:
    lines = doc.source.splitlines()
    return lines[line] if 0 <= line < len(lines) else ""

def previous_nonempty_line(doc: Document, line: int) -> tuple[int, str]:
    i = line - 1
    lines = doc.source.splitlines()
    while i >= 0:
        t = lines[i]
        if t.strip():
            return i, t
        i -= 1
    return -1, ""

def ident_prefix(s: str) -> str:
    i = len(s)
    while i > 0 and (s[i-1].isalnum() or s[i-1] in ("_","-")):
        i -= 1
    return s[i:]

# --- Completion Item Builders ----------------------------------------------

def items_section_snippets(pfx: str) -> List[CompletionItem]:
    p = pfx.lower(); out: List[CompletionItem] = []
    for label, snippet in SECTION_SNIPPETS:
        if p in label.lower():
            out.append(CompletionItem(
                label=label,
                kind=CompletionItemKind.Keyword,
                detail="snippet",
                insert_text=snippet,
                insert_text_format=InsertTextFormat.Snippet,
                sort_text="80_" + label
            ))
    return out

def items_simple_keywords(pfx: str) -> List[CompletionItem]:
    p = pfx.lower()
    return [
        CompletionItem(label=kw, kind=CompletionItemKind.Keyword, detail="keyword",
                        insert_text=kw, sort_text="90_"+kw)
        for kw in SIMPLE_KEYWORDS if p in kw.lower()
    ]

def items_builtins(pfx: str) -> List[CompletionItem]:
    p = pfx.lower(); out: List[CompletionItem] = []
    for name, kind, doc in BUILTIN_ACTIONS:
        if p in name.lower():
            # Important: escape braces in f-string so VS Code snippet ${1:args} stays literal
            out.append(CompletionItem(
                label=name,
                kind=CompletionItemKind.Function,
                detail=kind,
                documentation=MarkupContent(kind=MarkupKind.Markdown, value=doc),
                insert_text=f"{name}(${{1:args}})",
                insert_text_format=InsertTextFormat.Snippet,
                sort_text="10_"+name
            ))
    return out

def items_symbols(pfx: str, syms: Symbols) -> List[CompletionItem]:
    p = pfx.lower(); out: List[CompletionItem] = []
    for n in syms.actions:
        if p in n.lower():
            out.append(CompletionItem(label=n, kind=CompletionItemKind.Class, detail="action (declared)",
                                      insert_text=n, sort_text="05_"+n))
    for n in syms.events:
        if p in n.lower():
            out.append(CompletionItem(label=n, kind=CompletionItemKind.Event, detail="event (declared)",
                                      insert_text=n, sort_text="06_"+n))
    for n in syms.data:
        if p in n.lower():
            out.append(CompletionItem(label=n, kind=CompletionItemKind.Variable, detail="data (declared)",
                                      insert_text=n, sort_text="07_"+n))
    return out

# Context-aware suggestions inside Mission/During blocks
_DURING_RE = re.compile(r"^\s*During\s+([A-Za-z_][\w-]*)\s*:\s*$")
_ARROW_PREFIX_RE = re.compile(r"^\s*done\s*->\s*([A-Za-z_]\w*)?$")

def items_contextual(doc: Document, line: int, ch: int, syms: Symbols, pfx: str) -> List[CompletionItem]:
    out: List[CompletionItem] = []
    current_line = get_line_text(doc, line)
    line_before_cursor = current_line[:ch]

    # If we're on an indented line inside a During block and haven't typed an arrow yet,
    # suggest the transition snippet
    prev_i, prev_text = previous_nonempty_line(doc, line)
    if _DURING_RE.match(prev_text) and "->" not in line_before_cursor:
        if pfx.strip() == "" or "done".startswith(pfx):
            out.append(CompletionItem(
                label="done ->",
                kind=CompletionItemKind.Keyword,
                detail="transition",
                insert_text="done -> ${1:NextActionId}",
                insert_text_format=InsertTextFormat.Snippet,
                sort_text="20_done_arrow"
            ))

    # If the user has typed 'done -> <prefix>', offer action targets
    if "->" in line_before_cursor:
        m = _ARROW_PREFIX_RE.match(line_before_cursor.strip())
        if m is not None:
            out.extend(items_symbols(pfx, syms))  # only actions are in syms.actions but items_symbols filters by pfx

    return out

# --- LSP Server -------------------------------------------------------------
srv = LanguageServer(name="steeleagle-dsl-lsp", version="1.0.0")
logger.info("LanguageServer instance created")

@srv.feature(INITIALIZE)
def on_init(ls, _):
    logger.info("INITIALIZE request received")
    result = InitializeResult(
        capabilities=ServerCapabilities(
            text_document_sync=TextDocumentSyncOptions(
                open_close=True,
                change=TextDocumentSyncKind.Incremental
            ),
            completion_provider=CompletionOptions(
                # Broaden triggers so suggestions pop at useful times
                trigger_characters=[":", ">", "-", " ", "_", "(", ")", ",", "="]
            )
        )
    )
    logger.info("INITIALIZE response prepared")
    return result

logger.info("Creating Parser instance")
try:
    _parser = Parser()
    logger.info("Parser instance created successfully")
except Exception as e:
    logger.exception(f"Failed to create Parser: {e}")
    raise

@srv.feature(TEXT_DOCUMENT_COMPLETION)
def on_complete(ls, params: CompletionParams):
    logger.info(f"COMPLETION request for {params.text_document.uri} at line {params.position.line}, char {params.position.character}")
    try:
        doc = ls.workspace.get_document(params.text_document.uri)
        logger.debug(f"Document retrieved, length: {len(doc.source)}")

        # Parse with caching to survive transient errors while user is typing
        tree = parse_with_cache(_parser, doc.source)
        if tree:
            logger.debug("Document parsed successfully")
            syms = build_symbols(tree)
        else:
            syms = LAST_GOOD_SYMS or Symbols()
        logger.debug(f"Symbols collected: {len(syms.actions)} actions, {len(syms.events)} events, {len(syms.data)} data")

        line_pref = get_line_prefix(doc, params.position.line, params.position.character)
        pfx = ident_prefix(line_pref)
        logger.debug(f"Completion prefix: '{pfx}'")

        # Compose completion items
        items: List[CompletionItem] = []
        # Contextual suggestions first
        items += items_contextual(doc, params.position.line, params.position.character, syms, pfx)
        # Declared symbols
        items += items_symbols(pfx, syms)
        # Built-in actions (fixed snippet braces)
        items += items_builtins(pfx)
        # Section scaffolds and simple keywords
        items += items_section_snippets(pfx)
        items += items_simple_keywords(pfx)

        logger.info(f"Returning {len(items)} completion items")
        return CompletionList(is_incomplete=False, items=items)
    except Exception as e:
        logger.exception(f"Error in completion handler: {e}")
        return CompletionList(is_incomplete=False, items=[])

if __name__ == "__main__":
    logger.info("Starting LSP server via start_io()")
    try:
        srv.start_io()
    except Exception as e:
        logger.exception(f"Server crashed: {e}")
        raise
