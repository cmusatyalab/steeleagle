"""
SteelEagle SDK compiler integration

Wraps `steeleagle_sdk.dsl.build_mission()` 
(equivalent to `uv run dsl-compile YOUR_DSL_FILE`)

Design:
- If steeleagle_sdk is importable, use the authoritative SteelEagle SDK
  compiler. The static validator runs first to provide clearer, batched error
  messages for the MCP host model's retry loop before SDK compilation.
- If the SDK is not installed (e.g. CI without the dependency), degrade
  gracefully: `available` is False and callers fall back to the placeholder
  IR from validator.to_mission_ir().

Note: uv pip install steeleagle-sdk so that dsl/grammar/dronedsl.lark won't be missing.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class CompileResult:
    available: bool          
    ok: bool                 # Did compilation succeed? (False if unavailable)
    mission_json: dict[str, Any] | None
    error: str | None


def sdk_available() -> bool:
    try:
        from steeleagle_sdk.dsl import build_mission
        return True
    except Exception:
        return False


def compile_dsl(dsl_text: str) -> CompileResult:
    """Compile DSL with the authoritative SteelEagle SDK compiler, if available."""
    try:
        from steeleagle_sdk.dsl import build_mission
        from dataclasses import asdict
    except Exception as e:
        return CompileResult(
            available=False, ok=False, mission_json=None,
            error=f"steeleagle_sdk not available: {e}",
        )

    # Apply the same forgiving auto-fixes the validator uses (empty-stanza removal, trailing newline) so the real grammar sees clean input.
    from .validator import normalize_dsl
    dsl_text, _ = normalize_dsl(dsl_text)

    try:
        ir = build_mission(dsl_text)
        return CompileResult(
            available=True, ok=True, mission_json=asdict(ir), error=None,
        )
    except Exception as e:
        # Lark parse errors and Pydantic validation errors both land here.
        # Their messages include line/column context, which is what the LLM retry loop needs.
        return CompileResult(
            available=True, ok=False, mission_json=None,
            error=f"{type(e).__name__}: {e}",
        )
