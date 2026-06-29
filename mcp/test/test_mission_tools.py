import json
from pathlib import Path

from steeleagle_mcp.mission_tools import (
    compile_mission_dsl_payload,
    save_mission_artifacts_payload,
    translate_with_dsl_reference_payload,
)


VALID_DSL = """Actions:
    TakeOff take_off(take_off_altitude = 10.0)
    Land land()
Mission:
    Start take_off
    During take_off:
        done -> land
"""


INVALID_DSL = """Actions:
    FakeAction bad()
Mission:
    Start bad
"""


def test_translate_with_dsl_reference_payload_returns_reference():
    result = translate_with_dsl_reference_payload(
        "Take off to 10 meters, then land.",
        focus="basic",
        include_grammar=False,
        max_examples=1,
    )

    assert result["ok"], result["errors"]
    assert result["mode"] == "reference_only_no_server_llm"
    assert result["translator_role"] == "caller_llm"
    assert "TakeOff" in result["reference"]["schema"]["actions"]
    assert "Land" in result["reference"]["schema"]["actions"]
    assert result["reference"]["few_shot_examples"]
    assert result["candidate_validation"]["provided"] is False


def test_translate_with_dsl_reference_payload_validates_candidate():
    result = translate_with_dsl_reference_payload(
        "Take off to 10 meters, then land.",
        focus="basic",
        include_schema=False,
        include_examples=False,
        include_grammar=False,
        candidate_dsl=VALID_DSL,
    )

    assert result["ok"], result["errors"]
    assert result["candidate_validation"]["provided"]
    assert result["candidate_validation"]["ok"]
    assert result["candidate_validation"]["errors"] == []


def test_compile_mission_dsl_payload_success():
    result = compile_mission_dsl_payload(VALID_DSL)

    assert result["ok"], result["errors"]
    assert result["normalized_dsl"].endswith("\n")
    assert result["mission_json"]["start_action_id"] == "take_off"
    assert result["mission_json"]["actions"]["take_off"]["type_name"] == "TakeOff"
    assert result["compile_id"]
    assert result["dsl_hash"]


def test_compile_mission_dsl_payload_errors_are_structured():
    result = compile_mission_dsl_payload(INVALID_DSL)

    assert not result["ok"]
    assert result["mission_json"] is None
    assert result["errors"]
    assert any("FakeAction" in error for error in result["errors"])


def test_save_mission_artifacts_payload_writes_files(tmp_path: Path):
    compiled = compile_mission_dsl_payload(VALID_DSL)
    assert compiled["ok"], compiled["errors"]

    result = save_mission_artifacts_payload(
        compile_id=compiled["compile_id"],
        basename="test mission",
        output_dir=str(tmp_path),
        add_timestamp=False,
    )

    assert result["ok"], result["errors"]
    dsl_path = Path(result["dsl_path"])
    json_path = Path(result["json_path"])
    assert dsl_path.name == "test_mission.dsl"
    assert json_path.name == "test_mission.json"
    assert dsl_path.read_text(encoding="utf-8") == compiled["normalized_dsl"]
    assert (
        json.loads(json_path.read_text(encoding="utf-8"))["start_action_id"]
        == "take_off"
    )


def test_save_mission_artifacts_payload_accepts_manual_mission_json_text(tmp_path: Path):
    result = save_mission_artifacts_payload(
        dsl=VALID_DSL,
        compile_id="",
        mission_json_text=json.dumps(
            {
                "actions": {},
                "events": {},
                "data": {},
                "start_action_id": "take_off",
                "transitions": {},
            }
        ),
        basename="precompiled",
        output_dir=str(tmp_path),
        add_timestamp=False,
    )

    assert result["ok"], result["errors"]
    assert json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))[
        "start_action_id"
    ] == "take_off"


def test_save_mission_artifacts_payload_requires_compile_id(tmp_path: Path):
    result = save_mission_artifacts_payload(
        dsl=VALID_DSL,
        basename="missing-json",
        output_dir=str(tmp_path),
        add_timestamp=False,
    )

    assert not result["ok"]
    assert any("compile_id" in error for error in result["errors"])


def test_save_mission_artifacts_payload_rejects_mismatched_compile_id(
    tmp_path: Path,
):
    compiled = compile_mission_dsl_payload(VALID_DSL)
    assert compiled["ok"], compiled["errors"]

    changed_dsl = compiled["normalized_dsl"].replace(
        "Land land()", "ReturnToHome land()"
    )
    result = save_mission_artifacts_payload(
        dsl=changed_dsl,
        compile_id=compiled["compile_id"],
        basename="mismatch",
        output_dir=str(tmp_path),
        add_timestamp=False,
    )

    assert not result["ok"]
    assert any("does not match" in error for error in result["errors"])


def test_save_mission_artifacts_payload_refuses_overwrite(tmp_path: Path):
    compiled = compile_mission_dsl_payload(VALID_DSL)
    assert compiled["ok"], compiled["errors"]

    first = save_mission_artifacts_payload(
        compile_id=compiled["compile_id"],
        basename="mission",
        output_dir=str(tmp_path),
        add_timestamp=False,
    )
    assert first["ok"], first["errors"]

    second = save_mission_artifacts_payload(
        compile_id=compiled["compile_id"],
        basename="mission",
        output_dir=str(tmp_path),
        add_timestamp=False,
    )

    assert not second["ok"]
    assert any("Refusing to overwrite" in error for error in second["errors"])
