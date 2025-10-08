from __future__ import annotations
from pathlib import Path
from importlib import resources
from typing import List, Tuple, Optional
from pygls.server import LanguageServer
from pygls.workspace import Document
from pygls.lsp.methods import INITIALIZE, TEXT_DOCUMENT_COMPLETION
from pygls.lsp.types import (InitializeResult, CompletionParams, CompletionItem,
                             CompletionItemKind, TextDocumentSyncKind, CompletionOptions,
                             MarkupContent, MarkupKind, CompletionList)
from lark import Lark, Tree, Token, Visitor

DSL_KEYWORDS = ["mission","action","event","data","start","on","done","then","terminate","let","if","else","loop"]
BUILTIN_ACTIONS: List[Tuple[str,str,str]] = [
    ("TakeOff","Action","Arm and ascend"),
    ("SetVelocity","Action","Set velocity (m/s)"),
    ("SetGlobalPosition","Action","Go to GPS point"),
]

def grammar_path() -> Path:
    try:
        return Path(resources.files("steeleagle_sdk.dsl.grammar") / "dronedsl.lark")
    except Exception:
        # when running from the repo checkout
        repo_root = Path(__file__).resolve().parents[3]
        p = repo_root / "sdk" / "dsl" / "grammar" / "dronedsl.lark"
        if not p.is_file():
            raise FileNotFoundError(p)
        return p


class Parser:
    def __init__(self) -> None:
        g = grammar_path()
        self._p = Lark.open(str(g), rel_to=str(g.parent),
                            parser="lalr", keep_all_tokens=True,
                            propagate_positions=True, maybe_placeholders=True)
    def parse(self, text: str) -> Tree:
        return self._p.parse(text)

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

class Srv(LanguageServer): ...
srv = Srv()

@srv.feature(INITIALIZE)
def on_init(ls, _):
    return InitializeResult(capabilities={
        "textDocumentSync": TextDocumentSyncKind.Incremental,
        "completionProvider": CompletionOptions(trigger_characters=[".",":"," ","(",")",",","="])
    })

_parser = Parser()

@srv.feature(TEXT_DOCUMENT_COMPLETION)
def on_complete(ls, params: CompletionParams):
    doc = ls.workspace.get_document(params.text_document.uri)
    try:
        tree = _parser.parse(doc.source)
    except Exception:
        tree = None
    syms = build_symbols(tree)
    line_pref = get_line_prefix(doc, params.position.line, params.position.character)
    pfx = ident_prefix(line_pref)
    items = items_symbols(pfx, syms) + items_builtins(pfx) + items_keywords(pfx)
    return CompletionList(is_incomplete=False, items=items)

if __name__ == "__main__":
    srv.start_io()
