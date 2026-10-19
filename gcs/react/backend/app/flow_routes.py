"""FastAPI routes for the Plan page's Flow Builder -- see
docs/superpowers/specs/2026-10-16-gcs-flow-builder-design.md ("Amendment 2").

GET /catalog lists what one daemon could contribute to a flow: its vehicles
(each with the streams it produces) and its engines (with the source types
they accept and the events they emit). Which services exist comes from the
daemon's config; their types come from each service's plugin file
(DaemonBackend.get_plugin_tomls), read by app/plugin_toml.py. A service
whose plugin file is missing or unusable is reported untyped (`typed:
false`, with the reason in `problem`) with defaults the frontend treats as
matching everything. Like the /api/daemons routes, an unreachable daemon is
a 200 with `reachable: false`."""

from fastapi import APIRouter
from pydantic import BaseModel

from app import daemon_config
from app.daemon_backend import BackendFailure
from app.daemon_registry import open_backend
from app.eagled_routes import _daemon_doc, _failure
from app.plugin_toml import (
    RESULT_LABEL,
    TELEMETRY,
    PluginError,
    Stream,
    parse_driver,
    parse_engine,
)

router = APIRouter(prefix="/api/flows", tags=["flows"])

NO_PLUGIN_FILE = "no plugin file"
NOT_UTF8 = "plugin TOML is not UTF-8"


class CatalogStream(BaseModel):
    name: str
    kind: str
    type: str
    primary: bool
    description: str | None = None
    hres: int | None = None
    vres: int | None = None
    fps: int | None = None


class CatalogEvent(BaseModel):
    label: str
    type: str | None


class CatalogVehicle(BaseModel):
    name: str
    streams: list[CatalogStream]
    typed: bool
    problem: str | None = None


class CatalogEngine(BaseModel):
    name: str
    category: str | None
    accepts: list[str]
    events: list[CatalogEvent]
    typed: bool
    problem: str | None = None


class CatalogResponse(BaseModel):
    reachable: bool
    ok: bool = True
    vehicles: list[CatalogVehicle] = []
    engines: list[CatalogEngine] = []
    error: str | None = None


def _stream(s: Stream) -> CatalogStream:
    return CatalogStream(
        name=s.name,
        kind=s.kind,
        type=s.type,
        primary=s.primary,
        description=s.description or None,
        hres=s.hres,
        vres=s.vres,
        fps=s.fps,
    )


def _decode(raw: bytes | None) -> str:
    if raw is None:
        raise PluginError(NO_PLUGIN_FILE)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise PluginError(NOT_UTF8) from None


def _joined(problems: list[str]) -> str | None:
    return "; ".join(problems) or None


def _vehicle(name: str, raw: bytes | None) -> CatalogVehicle:
    try:
        driver = parse_driver(_decode(raw))
    except PluginError as e:
        # Every vehicle streams telemetry; its cameras are unknown.
        return CatalogVehicle(
            name=name, streams=[_stream(TELEMETRY)], typed=False, problem=str(e)
        )
    return CatalogVehicle(
        name=name,
        streams=[_stream(s) for s in driver.streams],
        typed=True,
        problem=_joined(driver.problems),
    )


def _engine(name: str, raw: bytes | None) -> CatalogEngine:
    try:
        engine = parse_engine(_decode(raw))
    except PluginError as e:
        return CatalogEngine(
            name=name,
            category=None,
            accepts=["*"],
            events=[CatalogEvent(label=RESULT_LABEL, type=None)],
            typed=False,
            problem=str(e),
        )
    return CatalogEngine(
        name=name,
        category=engine.category,
        accepts=engine.accepts,
        events=[CatalogEvent(label=e.label, type=e.type) for e in engine.events],
        typed=True,
        problem=_joined(engine.problems),
    )


@router.get("/catalog")
async def get_catalog(address: str) -> CatalogResponse:
    try:
        async with open_backend(address) as backend:
            text = await backend.get_configuration()
            tomls = await backend.get_plugin_tomls()
        doc = _daemon_doc(text)
    except BackendFailure as e:
        return _failure(CatalogResponse, e)

    vehicles, engines = [], []
    for category, section in daemon_config.list_sections(doc):
        name = section["name"]
        if category == "vehicle":
            vehicles.append(_vehicle(name, tomls.get(name)))
        elif category == "engine":
            engines.append(_engine(name, tomls.get(name)))
    return CatalogResponse(reachable=True, vehicles=vehicles, engines=engines)
