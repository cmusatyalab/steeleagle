import pytest

from app.compiler_config import REPO_ROOT
from app.plugin_toml import (
    TELEMETRY,
    TELEMETRY_TYPE,
    Event,
    PluginError,
    Stream,
    parse_driver,
    parse_engine,
)

EXAMPLES = REPO_ROOT / "config" / "examples"
RAW = "steeleagle_protocol/v1/messages/frame/RawFrame"
ENCODED = "steeleagle_protocol/v1/messages/frame/EncodedFrame"
DETECTION = "steeleagle_protocol/v1/messages/result/DetectionResult"
GENERIC = "steeleagle_protocol/v1/messages/result/GenericResult"


def _camera(name: str, type_: str | None = None) -> str:
    lines = ["[[driver.cameras]]", f'name = "{name}"']
    if type_:
        lines.append(f'type = "{type_}"')
    return "\n".join(lines) + "\n"


def _engine(input_type: str = f'"{RAW}"', extra: str = "") -> str:
    return (
        f'[engine]\ntype = "detection"\n[engine.input]\ntype = {input_type}\n' + extra
    )


# --- drivers ------------------------------------------------------------------


def test_example_driver_has_telemetry_first_then_its_camera():
    d = parse_driver((EXAMPLES / "driver.plugin.toml").read_text())

    assert d.streams == [
        TELEMETRY,
        Stream(
            "rgb",
            "camera",
            RAW,
            primary=True,
            description="Main RGB camera on gimbal",
            hres=1080,
            vres=720,
            fps=30,
        ),
    ]
    assert d.problems == []


def test_telemetry_is_the_implicit_stream():
    assert TELEMETRY == Stream("telemetry", "telemetry", TELEMETRY_TYPE)
    assert TELEMETRY_TYPE == "steeleagle_protocol/v1/messages/telemetry/Telemetry"


def test_driver_without_cameras_has_only_telemetry():
    assert parse_driver('[driver]\ntype = "copter"\n').streams == [TELEMETRY]


def test_camera_named_telemetry_is_dropped():
    d = parse_driver("[driver]\n" + _camera("telemetry", RAW))

    assert d.streams == [TELEMETRY]
    assert len(d.problems) == 1 and "telemetry" in d.problems[0]


def test_duplicate_camera_names_keep_the_first():
    d = parse_driver("[driver]\n" + _camera("rgb", RAW) + _camera("rgb", ENCODED))

    assert d.streams == [TELEMETRY, Stream("rgb", "camera", RAW)]
    assert len(d.problems) == 1 and '"rgb"' in d.problems[0]


def test_camera_without_type_is_dropped():
    d = parse_driver("[driver]\n" + _camera("rgb") + _camera("ir", RAW))

    assert d.streams == [TELEMETRY, Stream("ir", "camera", RAW)]
    assert len(d.problems) == 1 and '"rgb"' in d.problems[0]


@pytest.mark.parametrize(
    "text, match", [("[driver\n", "TOML"), ("[engine]\n", r"\[driver\]")]
)
def test_unusable_driver_files_raise(text, match):
    with pytest.raises(PluginError, match=match):
        parse_driver(text)


# --- engines ------------------------------------------------------------------


def test_example_engine():
    e = parse_engine((EXAMPLES / "engine.plugin.toml").read_text())

    assert e.category == "detection"
    assert e.accepts == [RAW]
    assert e.events == [Event("result", DETECTION), Event("dropped", GENERIC)]
    assert e.problems == []


def test_engine_input_may_be_a_list():
    e = parse_engine(_engine(f'["{TELEMETRY_TYPE}", "{RAW}"]'))

    assert e.accepts == [TELEMETRY_TYPE, RAW]


def test_engine_without_result_table_has_an_untyped_result():
    assert parse_engine(_engine()).events == [Event("result", None)]


def test_event_labelled_result_is_not_repeated():
    e = parse_engine(
        _engine(
            extra=f'[engine.result]\ntype = "{DETECTION}"\n'
            f'[[engine.events]]\nlabel = "result"\ntype = "{GENERIC}"\n'
        )
    )

    assert e.events == [Event("result", DETECTION)]


def test_event_without_label_is_skipped():
    e = parse_engine(
        _engine(
            extra=f'[[engine.events]]\ntype = "{GENERIC}"\n'
            '[[engine.events]]\nlabel = "dropped"\n'
        )
    )

    assert [ev.label for ev in e.events] == ["result", "dropped"]
    assert e.events[1] == Event("dropped", None)
    assert len(e.problems) == 1


@pytest.mark.parametrize(
    "text, match",
    [
        ("[engine\n", "TOML"),
        ('[driver]\ntype = "copter"\n', r"\[engine\]"),
        ('[engine]\ntype = "detection"\n', "input"),
        ("[engine]\n[engine.input]\ntype = 3\n", "input"),
        ("[engine]\n[engine.input]\ntype = []\n", "input"),
        ('[engine]\n[engine.input]\ntype = ["a", 1]\n', "input"),
    ],
)
def test_unusable_engine_files_raise(text, match):
    with pytest.raises(PluginError, match=match):
        parse_engine(text)


# --- wrongly shaped tables (final review) ------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        '[driver]\ncameras = "x"\n',
        '[driver]\n[driver.cameras]\nname = "rgb"\n',  # single brackets: a table
    ],
)
def test_driver_cameras_that_are_not_a_list_raise(text):
    with pytest.raises(PluginError, match="cameras"):
        parse_driver(text)


def test_camera_entries_that_are_not_tables_are_skipped():
    d = parse_driver(f'[driver]\ncameras = ["a", {{ name = "ir", type = "{RAW}" }}]\n')

    assert [s.name for s in d.streams] == ["telemetry", "ir"]
    assert len(d.problems) == 1


@pytest.mark.parametrize(
    "text, match",
    [
        ('[engine]\ninput = "x"\n', "input"),
        ("[engine]\ninput = 5\n", "input"),
        (f'[engine]\nresult = "x"\n[engine.input]\ntype = "{RAW}"\n', "result"),
        (f'[engine]\nevents = "x"\n[engine.input]\ntype = "{RAW}"\n', "events"),
    ],
)
def test_engine_tables_with_the_wrong_shape_raise(text, match):
    with pytest.raises(PluginError, match=match):
        parse_engine(text)


def test_event_entries_that_are_not_tables_are_skipped():
    e = parse_engine(
        f'[engine]\nevents = ["x", {{ label = "dropped" }}]\n[engine.input]\ntype = "{RAW}"\n'
    )

    assert [ev.label for ev in e.events] == ["result", "dropped"]
    assert len(e.problems) == 1
