from ..dsl.compiler.registry import _ACTIONS, _EVENTS, _DATA
from ..dsl.compiler.loader import load_all, print_report

from fastapi import FastAPI, HTTPException, Body
from typing import Dict, Type
from pydantic import BaseModel
from fastapi.responses import RedirectResponse, PlainTextResponse

summaries = load_all(force=True, show_trace=False)
print_report(summaries)

app = FastAPI(title="Task Definitions", version="0.1.0")

REGISTRIES: Dict[str, Dict[str, Type[BaseModel]]] = {
    "actions": _ACTIONS,
    "events": _EVENTS,
    "data": _DATA,
}

def _get_registry_or_404(category: str) -> Dict[str, Type[BaseModel]]:
    reg = REGISTRIES.get(category)
    if not isinstance(reg, dict):
        raise HTTPException(status_code=404, detail=f"Unknown category: {category}. Use one of {list(REGISTRIES)}")
    return reg

def _get_model_or_404(category: str, kind: str) -> Type[BaseModel]:
    reg = _get_registry_or_404(category)
    model = reg.get(kind)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown kind '{kind}' in '{category}'. Available: {list(reg)}")
    return model

@app.get("/schema")
def get_all_schemas():
    """Return JSON Schemas for all categories and kinds."""
    return {
        category: {kind: model.model_json_schema() for kind, model in registry.items()}
        for category, registry in REGISTRIES.items()
    }

@app.get("/schema/{category}")
def get_category_schema(category: str):
    """Return JSON Schemas for one category: actions | events | data."""
    reg = _get_registry_or_404(category)
    return {kind: model.model_json_schema() for kind, model in reg.items()}

@app.get("/schema/{category}/{kind}")
def get_kind_schema(category: str, kind: str):
    """Return JSON Schema for a single kind within a category."""
    model = _get_model_or_404(category, kind)
    return model.model_json_schema()


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return PlainTextResponse("", status_code=204)  # or serve a static file



