"""Deterministic DSL normalize / validate / compile pipeline.

Vendored slim subset of steeleagle-copilot's nl2dsl for MCP mission tools.
Does not include LLM translation, prompts, or Copilot session logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .compiler import compile_dsl
from .validator import ValidationError, normalize_dsl, to_mission_ir, validate


@dataclass
class PipelineOutcome:
    """Result of running one DSL candidate through normalize/validate/compile."""

    ok: bool
    dsl_code: str
    auto_fixes: list[str]
    errors: list[ValidationError]
    mission_ir: dict[str, Any] | None


def run_dsl_through_pipeline(dsl_code: str) -> PipelineOutcome:
    """Normalize, validate, and compile a DSL candidate."""
    dsl_code, auto_fixes = normalize_dsl(dsl_code)
    errors = validate(dsl_code)
    if errors:
        return PipelineOutcome(False, dsl_code, auto_fixes, errors, None)

    comp = compile_dsl(dsl_code)
    if comp.available and not comp.ok:
        return PipelineOutcome(
            False,
            dsl_code,
            auto_fixes,
            [ValidationError(None, f"real compiler error: {comp.error}")],
            None,
        )

    mission_ir = comp.mission_json if comp.ok else to_mission_ir(dsl_code)
    return PipelineOutcome(True, dsl_code, auto_fixes, [], mission_ir)
