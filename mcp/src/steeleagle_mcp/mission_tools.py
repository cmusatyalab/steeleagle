# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: 0BSD
"""Mission file tools for the SteelEagle MCP server.

This module provides DSL reference generation, deterministic validation and
compilation, and mission artifact persistence. Natural-language interpretation
is performed by the MCP caller's language model; the server supplies the
SteelEagle schema, grammar, examples, and compiler integration without requiring
a separate LLM provider or API key.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import uuid
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("server")


def _find_mcp_root() -> Path:
    """Find the mcp project root even when imported from an installed package."""
    here = Path(__file__).resolve()
    candidates = [Path.cwd(), *here.parents]
    for candidate in candidates:
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "steeleagle_mcp").is_dir()
        ):
            return candidate
    return here.parents[2]


_MCP_ROOT = _find_mcp_root()
_REPO_ROOT = _MCP_ROOT.parent
_SDK_SRC = _REPO_ROOT / "sdk" / "src"
_DEFAULT_MISSION_FILES_DIR = _MCP_ROOT / "mission_files"
_GRAMMAR_PATH = _SDK_SRC / "steeleagle_sdk" / "dsl" / "grammar" / "dronedsl.lark"
_EXAMPLES_DIR = _MCP_ROOT / "examples"

_VALID_FOCUS = {"all", "basic", "waypoints", "events", "actions"}
_MAX_COMPILED_MISSION_CACHE = 32
_COMPILED_MISSION_CACHE: dict[str, dict[str, Any]] = {}

_GENERATION_RULES = [
    "Generate a complete SteelEagle DSL file, not mission JSON.",
    "Use stanza order exactly: optional Data, required Actions, optional Events, required Mission.",
    "Omit Data or Events entirely when empty; never emit an empty Data: or Events: stanza.",
    "Declare nested objects in Data and reference them by bare identifier.",
    "Use bare identifiers for string-like enum/name values; do not quote strings.",
    "Use Start <action_name> with no colon.",
    "Put every transition inside a During <action_name>: block.",
    "Use done only as the reserved completion event; all other events must be declared in Events.",
    "Every action referenced by Start or transitions must be declared in Actions.",
    "Every declared action should be reachable from Start through transitions.",
    "For KML-backed paths, Waypoints.area must exactly match a KML Placemark name.",
    "For Waypoints algo=survey, include spacing, angle_degrees, and trigger_distance.",
    "For Waypoints algo=corridor, include spacing and angle_degrees.",
    "End missions by transitioning to a terminal action such as Land or ReturnToHome; do not invent end/stop states.",
]

_COMMON_MISTAKES = [
    {
        "bad": "Start: take_off",
        "good": "Start take_off",
        "reason": "Start is not a stanza and takes no colon.",
    },
    {
        "bad": "Waypoints path(area = 'PatrolZone', algo = 'edge', alt = 15.0)",
        "good": "Waypoints path(area = PatrolZone, algo = edge, alt = 15.0)",
        "reason": "The DSL grammar uses bare NAME tokens, not quoted strings.",
    },
    {
        "bad": "During patrol:\n    DetectionFound person_seen(target = person) -> track",
        "good": "Events:\n    DetectionFound person_seen(target = person)\nMission:\n    During patrol:\n        person_seen -> track",
        "reason": "Events must be declared in Events and referenced by event instance name.",
    },
    {
        "bad": "Data:\nActions:\n    Land land()\nEvents:\nMission:\n    Start land",
        "good": "Actions:\n    Land land()\nMission:\n    Start land",
        "reason": "Empty optional stanzas should be omitted.",
    },
    {
        "bad": "done -> end",
        "good": "done -> land",
        "reason": "There is no end state; declare and transition to a real action.",
    },
]


def _request_id() -> str:
    return uuid.uuid4().hex[:12]


def _err(category: str, message: str) -> str:
    return f"{category}: {message}"


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _canonical_dsl_text(text: str) -> str:
    return text if text.endswith("\n") else f"{text}\n"


def _remember_compiled_mission(
    *,
    normalized_dsl: str,
    mission_json: dict[str, Any],
) -> tuple[str, str]:
    compile_id = _request_id()
    dsl_text = _canonical_dsl_text(normalized_dsl)
    dsl_hash = _hash_text(dsl_text)
    _COMPILED_MISSION_CACHE[compile_id] = {
        "normalized_dsl": dsl_text,
        "dsl_hash": dsl_hash,
        "mission_json": mission_json,
        "created_at": datetime.now(UTC).isoformat(),
    }
    while len(_COMPILED_MISSION_CACHE) > _MAX_COMPILED_MISSION_CACHE:
        oldest_id = next(iter(_COMPILED_MISSION_CACHE))
        del _COMPILED_MISSION_CACHE[oldest_id]
    return compile_id, dsl_hash


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _ensure_sdk_path() -> None:
    if _SDK_SRC.is_dir() and str(_SDK_SRC) not in sys.path:
        sys.path.insert(0, str(_SDK_SRC))


def _load_nl2dsl_components() -> tuple[dict[str, Any] | None, str | None]:
    """Import the internal DSL normalization, validation, and compilation pipeline."""

    _ensure_sdk_path()

    try:
        from steeleagle_mcp.nl2dsl.pipeline import run_dsl_through_pipeline

        return {"run_dsl_through_pipeline": run_dsl_through_pipeline}, None
    except Exception as exc:
        return None, _err(
            "INTEGRATION_ERROR",
            "Failed to import the steeleagle_mcp.nl2dsl pipeline: "
            f"{exc}. Ensure steeleagle-mcp is installed (cd mcp && uv sync).",
        )


def _load_sdk_registry() -> tuple[dict[str, Any] | None, str | None]:
    _ensure_sdk_path()
    try:
        from steeleagle_sdk.dsl.compiler.loader import load_all
        from steeleagle_sdk.dsl.compiler.registry import _ACTIONS, _DATA, _EVENTS

        load_all()
        return {"actions": _ACTIONS, "events": _EVENTS, "data": _DATA}, None
    except Exception as exc:
        return None, _err("INTEGRATION_ERROR", str(exc))


def _resolve_ref(prop: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    if "$ref" not in prop:
        return prop
    ref_name = prop["$ref"].split("/")[-1]
    return defs.get(ref_name, prop)


def _unwrap_anyof(prop: dict[str, Any]) -> dict[str, Any]:
    if "anyOf" not in prop:
        return prop
    non_null = [item for item in prop["anyOf"] if item.get("type") != "null"]
    return non_null[0] if non_null else prop


def _ref_name(prop: dict[str, Any]) -> str | None:
    if "$ref" in prop:
        return prop["$ref"].split("/")[-1]
    for item in prop.get("anyOf", []):
        if "$ref" in item:
            return item["$ref"].split("/")[-1]
    return None


def _field_type(prop: dict[str, Any]) -> str:
    field_type = prop.get("type")
    if field_type in {"string", "number", "integer", "boolean", "array", "object"}:
        return field_type
    if "enum" in prop:
        return "string"
    return "object"


def _extract_fields(
    cls: type,
    *,
    include_nested: bool = True,
    _depth: int = 0,
) -> list[dict[str, Any]]:
    schema = cls.model_json_schema()
    defs = schema.get("$defs", {})
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: list[dict[str, Any]] = []

    for name, raw_prop in properties.items():
        prop = _resolve_ref(_unwrap_anyof(raw_prop), defs)
        prop = _resolve_ref(_unwrap_anyof(prop), defs)
        entry: dict[str, Any] = {
            "name": name,
            "type": _field_type(prop),
            "required": name in required,
            "description": raw_prop.get("description", prop.get("description", "")),
        }
        if "default" in raw_prop:
            entry["default"] = raw_prop["default"]
        if "enum" in prop:
            entry["enum"] = prop["enum"]

        ref_name = _ref_name(raw_prop)
        if ref_name:
            entry["object_type"] = ref_name

        if include_nested and _depth == 0 and prop.get("properties"):
            nested_required = set(prop.get("required", []))
            nested_fields = []
            for nested_name, nested_raw in prop.get("properties", {}).items():
                nested_prop = _resolve_ref(_unwrap_anyof(nested_raw), defs)
                nested_entry = {
                    "name": nested_name,
                    "type": _field_type(nested_prop),
                    "required": nested_name in nested_required,
                    "description": nested_raw.get(
                        "description", nested_prop.get("description", "")
                    ),
                }
                if "default" in nested_raw:
                    nested_entry["default"] = nested_raw["default"]
                if "enum" in nested_prop:
                    nested_entry["enum"] = nested_prop["enum"]
                nested_fields.append(nested_entry)
            entry["nested_fields"] = nested_fields

        fields.append(entry)

    return fields


def _first_doc_line(cls: type) -> str:
    return (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else ""


def _focus_allows(kind: str, class_name: str, focus: str) -> bool:
    if focus == "all":
        return True
    buckets = {
        "basic": {
            "actions": {"TakeOff", "Land", "ReturnToHome", "Hold", "Wait"},
            "events": {"TimeReached", "BatteryReached"},
            "data": {"Location"},
        },
        "waypoints": {
            "actions": {"TakeOff", "Patrol", "Track", "ReturnToHome", "Land"},
            "events": {"DetectionFound", "BatteryReached", "TimeReached"},
            "data": {"Waypoints", "Detection", "Location"},
        },
        "events": {
            "actions": {"TakeOff", "Patrol", "Track", "ReturnToHome", "Land", "Wait"},
            "events": None,
            "data": {"Detection", "Location", "Waypoints"},
        },
        "actions": {
            "actions": None,
            "events": set(),
            "data": {"Location", "Waypoints", "Detection"},
        },
    }
    allowed = buckets[focus][kind]
    return allowed is None or class_name in allowed


def _build_schema_reference(focus: str) -> tuple[dict[str, Any], str | None]:
    registry, error = _load_sdk_registry()
    if error:
        return {}, error

    out: dict[str, Any] = {"actions": {}, "events": {}, "data": {}}
    for kind, registry_key in (
        ("actions", "actions"),
        ("events", "events"),
        ("data", "data"),
    ):
        for _name, cls in sorted(registry[registry_key].items()):
            class_name = cls.__name__
            if not _focus_allows(kind, class_name, focus):
                continue
            out[kind][class_name] = {
                "description": _first_doc_line(cls),
                "fields": _extract_fields(cls),
            }
    return out, None


def _grammar_reference(include_grammar: bool) -> dict[str, Any]:
    summary = {
        "stanza_order": ["Data", "Actions", "Events", "Mission"],
        "required_stanzas": ["Actions", "Mission"],
        "optional_stanzas": ["Data", "Events"],
        "declaration": "ClassName instance_name(param = value, ...)",
        "mission_start": "Start <action_name>",
        "during_block": "During <action_name>: then indented transition lines",
        "transition": "<event_name> -> <action_name>",
        "values": ["NUMBER", "bare NAME", "array", "_ for None"],
        "name_token": "[A-Za-z_][A-Za-z0-9_]*",
    }
    reference = {"summary": summary}
    if include_grammar and _GRAMMAR_PATH.is_file():
        reference["ebnf"] = _GRAMMAR_PATH.read_text(encoding="utf-8")
    return reference


def _fallback_examples() -> list[dict[str, str]]:
    return [
        {
            "name": "takeoff_land.dsl",
            "dsl": (
                "Actions:\n"
                "    TakeOff take_off(take_off_altitude = 10.0)\n"
                "    Land land()\n"
                "Mission:\n"
                "    Start take_off\n"
                "    During take_off:\n"
                "        done -> land\n"
            ),
        },
        {
            "name": "patrol.dsl",
            "dsl": (
                "Data:\n"
                "    Waypoints patrol_path(alt = 15.0, area = PatrolZone, algo = edge)\n"
                "Actions:\n"
                "    TakeOff take_off(take_off_altitude = 10.0)\n"
                "    Patrol patrol(waypoints = patrol_path)\n"
                "    ReturnToHome return_to_home()\n"
                "Events:\n"
                "    BatteryReached battery_low(threshold = 40)\n"
                "Mission:\n"
                "    Start take_off\n"
                "    During take_off:\n"
                "        done -> patrol\n"
                "    During patrol:\n"
                "        done -> patrol\n"
                "        battery_low -> return_to_home\n"
            ),
        },
    ]


def _load_examples(include_examples: bool, focus: str, max_examples: int) -> list[dict[str, str]]:
    if not include_examples or max_examples < 1:
        return []

    examples: list[dict[str, str]] = []
    if _EXAMPLES_DIR.is_dir():
        preference = {
            "basic": ["takeoff_land.dsl", "delivery.dsl", "patrol.dsl"],
            "waypoints": ["patrol.dsl", "search_and_rescue.dsl", "delivery.dsl"],
            "events": ["patrol.dsl", "search_and_rescue.dsl", "delivery.dsl"],
            "actions": ["takeoff_land.dsl", "delivery.dsl", "patrol.dsl"],
            "all": ["takeoff_land.dsl", "patrol.dsl", "search_and_rescue.dsl", "delivery.dsl"],
        }
        paths = {path.name: path for path in _EXAMPLES_DIR.glob("*.dsl")}
        ordered_names = preference.get(focus, preference["all"])
        ordered = [paths[name] for name in ordered_names if name in paths]
        ordered += [path for name, path in sorted(paths.items()) if name not in ordered_names]
        for path in ordered[:max_examples]:
            examples.append({"name": path.name, "dsl": path.read_text(encoding="utf-8")})
    else:
        examples = _fallback_examples()[:max_examples]

    return examples


def _validate_candidate(candidate_dsl: str | None) -> dict[str, Any]:
    if not candidate_dsl:
        return {"provided": False}

    compiled = compile_mission_dsl_payload(
        candidate_dsl,
        return_ir=False,
        include_normalized_dsl=True,
    )
    return {
        "provided": True,
        "ok": compiled["ok"],
        "normalized_dsl": compiled["normalized_dsl"],
        "auto_fixes": compiled["auto_fixes"],
        "errors": compiled["errors"],
        "validation_summary": {
            "has_errors": bool(compiled["errors"]),
            "error_count": len(compiled["errors"]),
        },
    }


def translate_with_dsl_reference_payload(
    instruction: str,
    language: str = "auto",
    focus: str = "all",
    include_schema: bool = True,
    include_examples: bool = True,
    include_grammar: bool = True,
    include_common_mistakes: bool = True,
    candidate_dsl: str | None = None,
    max_examples: int = 4,
) -> dict[str, Any]:
    """Return DSL translation reference for the caller LLM, optionally validating a candidate."""
    request_id = _request_id()

    if not isinstance(instruction, str) or not instruction.strip():
        return {
            "ok": False,
            "errors": [_err("INPUT_ERROR", "`instruction` is required")],
            "request_id": request_id,
        }
    if language not in {"auto", "zh", "en"}:
        return {
            "ok": False,
            "errors": [_err("INPUT_ERROR", "`language` must be one of auto, zh, en")],
            "request_id": request_id,
        }
    if focus not in _VALID_FOCUS:
        return {
            "ok": False,
            "errors": [
                _err("INPUT_ERROR", f"`focus` must be one of {sorted(_VALID_FOCUS)}")
            ],
            "request_id": request_id,
        }

    logger.info(
        "mission tool translate_with_dsl_reference request_id=%s instruction_hash=%s focus=%s",
        request_id,
        _hash_text(instruction),
        focus,
    )

    schema, schema_error = ({}, None)
    if include_schema:
        schema, schema_error = _build_schema_reference(focus)
        if schema_error:
            return {"ok": False, "errors": [schema_error], "request_id": request_id}

    candidate_validation = _validate_candidate(candidate_dsl)
    payload = {
        "ok": True,
        "mode": "reference_only_no_server_llm",
        "translator_role": "caller_llm",
        "instruction": instruction.strip(),
        "language": language,
        "focus": focus,
        "reference": {
            "grammar": _grammar_reference(include_grammar),
            "generation_rules": _GENERATION_RULES,
            "common_mistakes": _COMMON_MISTAKES if include_common_mistakes else [],
            "schema": schema,
            "few_shot_examples": _load_examples(
                include_examples=include_examples,
                focus=focus,
                max_examples=max_examples,
            ),
        },
        "candidate_validation": candidate_validation,
        "recommended_workflow": [
            "Use the instruction plus this reference to write a complete mission.dsl.",
            "Call compile_mission_dsl with the DSL.",
            "If compile_mission_dsl returns errors, revise the DSL and call it again.",
            "After compile succeeds, call save_mission_files with the compile_id from compile_mission_dsl.",
            "Do not upload or start the generated mission unless the user explicitly asks after review.",
        ],
        "errors": [],
        "request_id": request_id,
    }

    logger.info(
        "mission tool translate_with_dsl_reference request_id=%s ok=True candidate_provided=%s",
        request_id,
        candidate_validation["provided"],
    )
    return payload


def compile_mission_dsl_payload(
    dsl: str,
    return_ir: bool = True,
    include_normalized_dsl: bool = True,
) -> dict[str, Any]:
    """Normalize, validate, and compile SteelEagle DSL into mission JSON."""
    request_id = _request_id()

    if not isinstance(dsl, str) or not dsl.strip():
        return {
            "ok": False,
            "normalized_dsl": "",
            "mission_json": None,
            "mission_ir": None,
            "compile_id": "",
            "dsl_hash": "",
            "auto_fixes": [],
            "errors": [_err("INPUT_ERROR", "`dsl` is required")],
            "request_id": request_id,
        }

    components, import_error = _load_nl2dsl_components()
    if import_error:
        return {
            "ok": False,
            "normalized_dsl": dsl,
            "mission_json": None,
            "mission_ir": None,
            "compile_id": "",
            "dsl_hash": _hash_text(dsl),
            "auto_fixes": [],
            "errors": [import_error],
            "request_id": request_id,
        }

    logger.info(
        "mission tool compile_mission_dsl request_id=%s dsl_hash=%s",
        request_id,
        _hash_text(dsl),
    )
    try:
        outcome = components["run_dsl_through_pipeline"](dsl)
    except Exception as exc:
        logger.exception("compile_mission_dsl failed request_id=%s", request_id)
        return {
            "ok": False,
            "normalized_dsl": dsl,
            "mission_json": None,
            "mission_ir": None,
            "compile_id": "",
            "dsl_hash": _hash_text(dsl),
            "auto_fixes": [],
            "errors": [_err("COMPILE_ERROR", str(exc))],
            "request_id": request_id,
        }

    mission_json = _jsonable(outcome.mission_ir) if outcome.ok else None
    compile_id = ""
    dsl_hash = _hash_text(_canonical_dsl_text(outcome.dsl_code))
    if outcome.ok and mission_json:
        compile_id, dsl_hash = _remember_compiled_mission(
            normalized_dsl=outcome.dsl_code,
            mission_json=mission_json,
        )
    errors = [str(e) for e in outcome.errors]
    payload = {
        "ok": outcome.ok,
        "normalized_dsl": outcome.dsl_code if include_normalized_dsl else "",
        "mission_json": mission_json,
        "mission_ir": mission_json if return_ir else None,
        "compile_id": compile_id,
        "dsl_hash": dsl_hash,
        "auto_fixes": outcome.auto_fixes,
        "errors": errors,
        "request_id": request_id,
    }
    logger.info(
        "mission tool compile_mission_dsl request_id=%s ok=%s error_count=%d",
        request_id,
        outcome.ok,
        len(errors),
    )
    return payload


def _coerce_mission_json_text(value: str | None) -> tuple[Any | None, str | None]:
    if value is None or value == "":
        return None, None
    if isinstance(value, str):
        try:
            return json.loads(value), None
        except json.JSONDecodeError as exc:
            return None, _err(
                "INPUT_ERROR", f"`mission_json_text` is not valid JSON: {exc}"
            )
    return None, _err("INPUT_ERROR", "`mission_json_text` must be a JSON string")


def _resolve_output_dir(output_dir: str | None) -> Path:
    if not output_dir:
        return _DEFAULT_MISSION_FILES_DIR

    path = Path(output_dir).expanduser()
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == _MCP_ROOT.name:
        return (_REPO_ROOT / path).resolve()
    return (_MCP_ROOT / path).resolve()


def _safe_basename(basename: str | None) -> str:
    raw = (basename or "mission").strip()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-")
    return safe or "mission"


def save_mission_files_payload(
    compile_id: str = "",
    dsl: str = "",
    mission_json_text: str = "",
    basename: str = "mission",
    output_dir: str = "",
    overwrite: bool = False,
    add_timestamp: bool = True,
) -> dict[str, Any]:
    """Write mission DSL and JSON files to disk."""
    request_id = _request_id()

    notes: list[str] = []
    parsed_json: Any | None = None
    dsl_text = ""
    compile_id = (compile_id or "").strip()

    if compile_id:
        cached = _COMPILED_MISSION_CACHE.get(compile_id)
        if cached is None:
            return {
                "ok": False,
                "dsl_path": None,
                "json_path": None,
                "written_files": [],
                "compile_id": compile_id,
                "errors": [
                    _err(
                        "INPUT_ERROR",
                        "Unknown or expired `compile_id`. Call compile_mission_dsl "
                        "again and pass the returned `compile_id` to save_mission_files.",
                    )
                ],
                "request_id": request_id,
            }

        if dsl:
            provided_hash = _hash_text(_canonical_dsl_text(dsl))
        else:
            provided_hash = cached["dsl_hash"]
        if dsl and provided_hash != cached["dsl_hash"]:
            return {
                "ok": False,
                "dsl_path": None,
                "json_path": None,
                "written_files": [],
                "compile_id": compile_id,
                "errors": [
                    _err(
                        "INPUT_ERROR",
                        "`dsl` does not match the normalized DSL compiled for this "
                        "`compile_id`. Pass compile_mission_dsl.normalized_dsl, or "
                        "call compile_mission_dsl again for the edited DSL.",
                    )
                ],
                "request_id": request_id,
            }

        parsed_json = cached["mission_json"]
        dsl_text = cached["normalized_dsl"]
        if mission_json_text:
            notes.append("Ignored `mission_json_text` because `compile_id` was provided.")
    else:
        if not isinstance(dsl, str) or not dsl.strip():
            return {
                "ok": False,
                "dsl_path": None,
                "json_path": None,
                "written_files": [],
                "compile_id": "",
                "errors": [
                    _err(
                        "INPUT_ERROR",
                        "`compile_id` is required. Call compile_mission_dsl first and "
                        "pass its `compile_id` here.",
                    )
                ],
                "request_id": request_id,
            }

        parsed_json, json_error = _coerce_mission_json_text(mission_json_text)
        if json_error:
            return {
                "ok": False,
                "dsl_path": None,
                "json_path": None,
                "written_files": [],
                "compile_id": "",
                "errors": [json_error],
                "request_id": request_id,
            }
        if parsed_json is None:
            return {
                "ok": False,
                "dsl_path": None,
                "json_path": None,
                "written_files": [],
                "compile_id": "",
                "errors": [
                    _err(
                        "INPUT_ERROR",
                        "`compile_id` is required. Call compile_mission_dsl first and "
                        "pass its `compile_id` here.",
                    )
                ],
                "request_id": request_id,
            }
        notes.append(
            "Used manual mission_json_text fallback; prefer compile_id from "
            "compile_mission_dsl."
        )
        dsl_text = _canonical_dsl_text(dsl)

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    name = _safe_basename(basename)
    if add_timestamp:
        name = f"{name}-{timestamp}"

    try:
        mission_files_dir = _resolve_output_dir(output_dir)
        mission_files_dir.mkdir(parents=True, exist_ok=True)

        dsl_path = mission_files_dir / f"{name}.dsl"
        json_path = mission_files_dir / f"{name}.json"
        existing = [str(p) for p in (dsl_path, json_path) if p.exists()]
        if existing and not overwrite:
            return {
                "ok": False,
                "dsl_path": None,
                "json_path": None,
                "written_files": [],
                "compile_id": compile_id,
                "errors": [
                    _err(
                        "IO_ERROR",
                        "Refusing to overwrite existing mission file(s): "
                        + ", ".join(existing),
                    )
                ],
                "request_id": request_id,
            }

        dsl_path.write_text(dsl_text, encoding="utf-8")
        json_path.write_text(
            json.dumps(parsed_json, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        logger.exception("save_mission_files failed request_id=%s", request_id)
        return {
            "ok": False,
            "dsl_path": None,
            "json_path": None,
            "written_files": [],
            "compile_id": compile_id,
            "errors": [_err("IO_ERROR", str(exc))],
            "request_id": request_id,
        }

    written = [str(dsl_path), str(json_path)]
    logger.info(
        "mission tool save_mission_files request_id=%s ok=True file_paths=%s",
        request_id,
        written,
    )
    return {
        "ok": True,
        "dsl_path": str(dsl_path),
        "json_path": str(json_path),
        "written_files": written,
        "compile_id": compile_id,
        "notes": notes,
        "errors": [],
        "request_id": request_id,
    }
