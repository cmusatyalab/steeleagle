from __future__ import annotations

from dataclasses import dataclass
import inspect
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union
from typing import get_args, get_origin

from lsprotocol.types import CompletionItem, CompletionItemKind, InsertTextFormat, MarkupContent, MarkupKind
from pydantic import BaseModel

from ...dsl.compiler import loader, registry

logger = logging.getLogger(__name__)

DATA_COMPLETION_KIND = getattr(CompletionItemKind, "Struct", CompletionItemKind.Class)
INSERT_TEXT_FORMAT_SNIPPET = InsertTextFormat.Snippet


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


def _is_model_type(tp: Any) -> bool:
    try:
        return isinstance(tp, type) and issubclass(tp, BaseModel)
    except Exception:
        return False


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Union:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _words(name: str) -> str:
    return name.replace("_", " ").strip()


def _format_type_hint(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type):
            if annotation.__module__ == "builtins":
                return annotation.__name__
            return f"{annotation.__module__}.{annotation.__name__}"
        return str(annotation).replace("typing.", "")
    if origin is Union:
        return " | ".join(_format_type_hint(arg) for arg in get_args(annotation))
    if origin in (list, List):
        args = get_args(annotation)
        inner = args[0] if args else Any
        return f"List[{_format_type_hint(inner)}]"
    return str(annotation).replace("typing.", "")


def _placeholder_hint(name: str, annotation: Any) -> str:
    base = _words(name)
    plain = _unwrap_optional(annotation)

    if _is_model_type(plain):
        return f"<{plain.__name__} id>"

    origin = get_origin(plain)
    if origin in (list, List):
        args = get_args(plain)
        inner = args[0] if args else Any
        inner_plain = _unwrap_optional(inner)
        if _is_model_type(inner_plain):
            return f"<list of {inner_plain.__name__} ids>"
        return f"<list of {base}>"

    if plain in (int, float):
        return f"<{base} value>"
    if plain is bool:
        return "<true|false>"
    if plain is str:
        return f"<{base} text>"
    if plain is None:
        return "<none>"

    return f"<{base}>" if base else "<value>"


def _identifier_placeholder(cls: type[BaseModel]) -> str:
    return f"<{cls.__name__} name>"


def _render_constructor(name: str, id_placeholder: Optional[str], attr_lines: List[str]) -> str:
    head = name if id_placeholder is None else f"{name} {id_placeholder}"
    if attr_lines:
        return f"{head}({', '.join(attr_lines)})"
    return head


def _render_inline_constructor(name: str, arg_placeholders: List[str]) -> str:
    if arg_placeholders:
        return f"{name}({', '.join(arg_placeholders)})"
    return f"{name}()"


def _build_attr_lines(
    model_cls: type[BaseModel],
    start_index: int,
) -> Tuple[List[str], List[str], List[str], List[str], List[Tuple[str, str, bool]], List[str]]:
    required_lines: List[str] = []
    optional_lines: List[str] = []
    required_names: List[str] = []
    optional_names: List[str] = []
    field_docs: List[Tuple[str, str, bool]] = []
    arg_placeholders: List[str] = []
    idx = start_index
    for field_name, field_info in getattr(model_cls, "model_fields", {}).items():
        placeholder = _placeholder_hint(field_name, field_info.annotation)
        arg_placeholders.append(f"${{{idx}:{placeholder}}}")
        snippet = f"{field_name} = ${{{idx}:{placeholder}}}"
        idx += 1
        is_required = field_info.is_required()
        field_docs.append((field_name, _format_type_hint(field_info.annotation), is_required))
        if is_required:
            required_lines.append(snippet)
            required_names.append(field_name)
        else:
            optional_lines.append(snippet)
            optional_names.append(field_name)
    return required_lines, optional_lines, required_names, optional_names, field_docs, arg_placeholders


def _build_documentation(cls: type[BaseModel], field_docs: List[Tuple[str, str, bool]]) -> Optional[str]:
    doc_lines: List[str] = []
    raw_doc = inspect.cleandoc(cls.__doc__ or "")
    if raw_doc:
        doc_lines.append(raw_doc)
    if field_docs:
        if doc_lines:
            doc_lines.append("")
        doc_lines.append("**Fields**")
        for name, type_repr, is_required in field_docs:
            requirement = "required" if is_required else "optional"
            doc_lines.append(f"- `{name}` ({type_repr}) - {requirement}")
    return "\n".join(doc_lines) if doc_lines else None


def _create_model_completion(
    kind: str,
    cls: type[BaseModel],
    sort_prefix: str,
) -> Tuple[RegistryCompletion, Optional[RegistryCompletion]]:
    required_lines, optional_lines, required_names, optional_names, field_docs, arg_placeholders = _build_attr_lines(cls, 2)
    attr_lines = required_lines + optional_lines
    identifier = f"${{1:{_identifier_placeholder(cls)}}}"
    documentation = _build_documentation(cls, field_docs)

    detail_bits = [f"{kind} (SDK)"]
    if required_names:
        detail_bits.append("required: " + ", ".join(required_names))
    if optional_names:
        detail_bits.append("optional: " + ", ".join(optional_names))

    head_kind = CompletionItemKind.Class if kind in ("action", "event") else DATA_COMPLETION_KIND
    completion = RegistryCompletion(
        label=cls.__name__,
        insert_text=_render_constructor(cls.__name__, identifier, attr_lines),
        detail=" — ".join(detail_bits),
        documentation=documentation,
        sort_text=f"{sort_prefix}_{cls.__name__}",
        kind=head_kind,
    )

    inline = None
    if kind == "data":
        inline = RegistryCompletion(
            label=cls.__name__,
            insert_text=_render_inline_constructor(cls.__name__, arg_placeholders),
            detail=f"inline data constructor ({cls.__name__})",
            documentation=documentation,
            sort_text=f"04_{cls.__name__}",
            kind=DATA_COMPLETION_KIND,
        )

    return completion, inline


def _iter_registry_classes(storage: Dict[str, Any]) -> Iterable[type[BaseModel]]:
    seen: Set[type[BaseModel]] = set()
    for value in storage.values():
        if isinstance(value, type) and issubclass(value, BaseModel) and value not in seen:
            seen.add(value)
            yield value


def _build_registry_lookup() -> Tuple[Dict[str, List[RegistryCompletion]], List[RegistryCompletion]]:
    completions: Dict[str, List[RegistryCompletion]] = {"actions": [], "events": [], "data": []}
    inline_data: List[RegistryCompletion] = []

    for cls in sorted(_iter_registry_classes(getattr(registry, "_ACTIONS", {})), key=lambda c: c.__name__):
        comp, _ = _create_model_completion("action", cls, "01")
        completions["actions"].append(comp)

    for cls in sorted(_iter_registry_classes(getattr(registry, "_EVENTS", {})), key=lambda c: c.__name__):
        comp, _ = _create_model_completion("event", cls, "02")
        completions["events"].append(comp)

    for cls in sorted(_iter_registry_classes(getattr(registry, "_DATA", {})), key=lambda c: c.__name__):
        comp, inline = _create_model_completion("data", cls, "03")
        completions["data"].append(comp)
        if inline:
            inline_data.append(inline)

    return completions, inline_data


_REGISTRY_COMPLETIONS: Optional[Dict[str, List[RegistryCompletion]]] = None
_INLINE_DATA_COMPLETIONS: Optional[List[RegistryCompletion]] = None
_INITIALIZED = False


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
