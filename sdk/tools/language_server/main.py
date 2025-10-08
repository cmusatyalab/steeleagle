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
    TextDocumentSyncOptions
)
from lark import Lark, Tree, Token, Visitor
import logging

# Configure logging to file for debugging
logging.basicConfig(
    filename='./steeleagle_lsp.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DSL_KEYWORDS = ["mission","action","event","data","start","on","done","then","terminate","let","if","else","loop"]
BUILTIN_ACTIONS: List[Tuple[str,str,str]] = [
    ("TakeOff","Action","Arm and ascend"),
    ("SetVelocity","Action","Set velocity (m/s)"),
    ("SetGlobalPosition","Action","Go to GPS point"),
]


class Parser:
    def __init__(self) -> None:
        try:
            logger.info("Initializing Parser")
            grammar_file = resources.files("steeleagle_sdk.dsl.grammar") / "dronedsl.lark"
            logger.info(f"Grammar file path: {grammar_file}")
            
            with resources.as_file(grammar_file) as g:
                logger.info(f"Resolved grammar file: {g}")
                self._p = Lark.open(str(g),
                                    parser="lalr", keep_all_tokens=True,
                                    propagate_positions=True, maybe_placeholders=True)
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
    # adjust rule names if different in your grammar
    def __init__(self, syms: Symbols) -> None:
        self.syms = syms
    def action_decl(self, tree: Tree) -> None:
        for ch in tree.children:
            if isinstance(ch, Token) and ch.type in {"NAME","CNAME","IDENT"}:
                self.syms.actions.append(str(ch)); break
    def event_decl(self, tree: Tree) -> None:
        for ch in tree.children:
            if isinstance(ch, Token) and ch.type in {"NAME","CNAME","IDENT"}:
                self.syms.events.append(str(ch)); break
    def data_decl(self, tree: Tree) -> None:
        for ch in tree.children:
            if isinstance(ch, Token) and ch.type in {"NAME","CNAME","IDENT"}:
                self.syms.data.append(str(ch)); break

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

def get_line_prefix(doc: Document, line: int, ch: int) -> str:
    lines = doc.source.splitlines()
    return lines[line][:ch] if 0 <= line < len(lines) else ""

def ident_prefix(s: str) -> str:
    i = len(s)
    while i > 0 and (s[i-1].isalnum() or s[i-1] in ("_","-")):
        i -= 1
    return s[i:]

def items_keywords(pfx: str) -> List[CompletionItem]:
    p = pfx.lower()
    return [CompletionItem(label=kw, kind=CompletionItemKind.Keyword, detail="keyword",
                           insert_text=kw, sort_text="90_"+kw) for kw in DSL_KEYWORDS if p in kw.lower()]

def items_builtins(pfx: str) -> List[CompletionItem]:
    p = pfx.lower(); out: List[CompletionItem] = []
    for name, kind, doc in BUILTIN_ACTIONS:
        if p in name.lower():
            out.append(CompletionItem(label=name, kind=CompletionItemKind.Function, detail=kind,
                                      documentation=MarkupContent(kind=MarkupKind.Markdown, value=doc),
                                      insert_text=f"{name}(${1:args})", insert_text_format=2, sort_text="10_"+name))
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
                trigger_characters=[".",":"," ","(",")",",","="]
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
        
        try:
            tree = _parser.parse(doc.source)
            logger.debug("Document parsed successfully")
        except Exception as e:
            logger.debug(f"Parse failed: {e}")
            tree = None
        
        syms = build_symbols(tree)
        logger.debug(f"Symbols collected: {len(syms.actions)} actions, {len(syms.events)} events, {len(syms.data)} data")
        
        line_pref = get_line_prefix(doc, params.position.line, params.position.character)
        pfx = ident_prefix(line_pref)
        logger.debug(f"Completion prefix: '{pfx}'")
        
        items = items_symbols(pfx, syms) + items_builtins(pfx) + items_keywords(pfx)
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