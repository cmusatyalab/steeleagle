"""Reads what the Flow Builder needs from eagled plugin files (the
`*.plugin.toml` each service ships; examples in config/examples/) -- see
"Amendment 2" in docs/superpowers/specs/2026-10-16-gcs-flow-builder-design.md.

A driver's plugin file gives a vehicle's streams: one per [[driver.cameras]]
entry, after the `telemetry` stream every vehicle has. An engine's gives the
source types it accepts ([engine.input] type) and the events it emits:
`result` first, then each [[engine.events]] label. Other tables ([[args]],
[driver.supported], ...) belong to the Configure form and the compiler and
are ignored here.

A file that can't supply this raises PluginError (the catalog then reports
the service untyped); a single bad entry is dropped and described in
`problems` instead."""

import tomllib
from dataclasses import dataclass, field

TELEMETRY_TYPE = "steeleagle_protocol/v1/messages/telemetry/Telemetry"
RESULT_LABEL = "result"


class PluginError(ValueError):
    """The plugin file can't supply a stream list or an engine's types."""


@dataclass(frozen=True)
class Stream:
    name: str
    kind: str  # "telemetry" | "camera"
    type: str
    primary: bool = False
    description: str = ""
    hres: int | None = None
    vres: int | None = None
    fps: int | None = None


@dataclass(frozen=True)
class Event:
    label: str
    type: str | None


@dataclass(frozen=True)
class Driver:
    streams: list[Stream]
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Engine:
    category: str | None
    accepts: list[str]
    events: list[Event]
    problems: list[str] = field(default_factory=list)


# The stream every vehicle has, whatever its driver declares.
TELEMETRY = Stream("telemetry", "telemetry", TELEMETRY_TYPE)


def _table(text: str, name: str) -> dict:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise PluginError(f"plugin TOML is invalid: {e}") from e
    table = data.get(name)
    if not isinstance(table, dict):
        raise PluginError(f"plugin file has no [{name}] table")
    return table


def _subtable(parent: dict, key: str, where: str) -> dict:
    """parent[key] as a table ({} when absent); any other shape is fatal."""
    value = parent.get(key, {})
    if not isinstance(value, dict):
        raise PluginError(f"{where} must be a table")
    return value


def _entries(parent: dict, key: str, where: str) -> list:
    """parent[key] as a list ([] when absent); any other shape is fatal."""
    value = parent.get(key, [])
    if not isinstance(value, list):
        raise PluginError(f"{where} must be a list of tables ([[{where[1:-1]}]])")
    return value


def _int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse_driver(text: str) -> Driver:
    driver = _table(text, "driver")
    streams = [TELEMETRY]
    problems = []
    for camera in _entries(driver, "cameras", "[driver.cameras]"):
        if not isinstance(camera, dict):
            problems.append("a camera entry is not a table; skipped")
            continue
        name = camera.get("name")
        type_ = camera.get("type")
        if not isinstance(name, str) or not name:
            problems.append("a camera has no name; skipped")
        elif not isinstance(type_, str) or not type_:
            problems.append(f'camera "{name}" has no type; skipped')
        elif any(s.name == name for s in streams):
            problems.append(f'camera "{name}" duplicates the {name} stream; skipped')
        else:
            description = camera.get("description")
            streams.append(
                Stream(
                    name,
                    "camera",
                    type_,
                    primary=camera.get("primary") is True,
                    description=description if isinstance(description, str) else "",
                    hres=_int(camera.get("hres")),
                    vres=_int(camera.get("vres")),
                    fps=_int(camera.get("fps")),
                )
            )
    return Driver(streams, problems)


def _accepts(engine: dict) -> list[str]:
    value = _subtable(engine, "input", "[engine.input]").get("type")
    if isinstance(value, str) and value:
        return [value]
    if (
        isinstance(value, list)
        and value
        and all(isinstance(t, str) and t for t in value)
    ):
        return list(value)
    raise PluginError("[engine.input] type must be a message type or a list of them")


def parse_engine(text: str) -> Engine:
    engine = _table(text, "engine")
    accepts = _accepts(engine)
    category = engine.get("type")
    result_type = _subtable(engine, "result", "[engine.result]").get("type")
    events = [
        Event(RESULT_LABEL, result_type if isinstance(result_type, str) else None)
    ]
    problems = []
    for entry in _entries(engine, "events", "[engine.events]"):
        if not isinstance(entry, dict):
            problems.append("an event entry is not a table; skipped")
            continue
        label = entry.get("label")
        type_ = entry.get("type")
        if not isinstance(label, str) or not label:
            problems.append("an event has no label; skipped")
        elif any(e.label == label for e in events):
            continue
        else:
            events.append(Event(label, type_ if isinstance(type_, str) else None))
    return Engine(
        category if isinstance(category, str) else None, accepts, events, problems
    )
