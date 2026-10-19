"""FastAPI routes for the Orchestrate page's daemon view -- see
docs/superpowers/specs/2026-10-15-gcs-generic-plugins-design.md.

Routes reach a daemon through app/daemon_registry.open_backend: a mock for
`mock://` addresses, the revised eagled gRPC API otherwise. Every route
returns HTTP 200; `reachable` tells an unreachable daemon (an ordinary
state for this UI) from a failed operation (`ok: false` + `error`). Only
request validation and TOML errors in the request are 422s.

eagled's Configure replaces the whole config and restarts the daemon, so
the GCS edits the whole document: GET /config returns it (as raw TOML and
as a form), PUT /config sends it back. The client sends the config_hash it
loaded, and a save is refused as a conflict if the daemon's config has
changed since. That check runs here, not atomically in eagled, so it is
best-effort until eagled exposes a config version."""

import asyncio
import json
import shutil
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app import daemon_config
from app.daemon_backend import (
    BackendFailure,
    DaemonError,
    DaemonUnreachable,
    RESTARTABLE_CATEGORIES,
    NotSupported,
    ServiceRef,
    ServiceState,
)
from app.daemon_registry import MOCK_DISCOVERED, mock_enabled, open_backend

router = APIRouter(prefix="/api/daemons", tags=["daemons"])

# Tag applied to eagled's tsnet node -- not by this codebase, but by the
# reusable Tailscale auth key eagled authenticates with (configured in the
# tailnet's admin console, outside this repo). Discovery has no way to see
# an operator-overridden `-control-port`, so it assumes every instance kept
# eagled's default (cmd/eagled/daemon.go's DefaultControlPort).
DAEMON_TAILSCALE_TAG = "tag:steeleagle-daemon"
DEFAULT_CONTROL_PORT = 9090

CONFLICT_MESSAGE = (
    "the daemon's config changed since it was loaded; reload and try again"
)

NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
NAME_MAX_LENGTH = 64
# Keys the GCS writes itself; letting instance_fields / plugin.extra carry
# them would bypass the name and duplicate checks.
RESERVED_INSTANCE_KEYS = {"name", "plugin"}
MANAGED_PLUGIN_KEYS = {"id", "plugin", "runtime", "url", "image", "tag", "args"}

Category = Literal[
    "vehicle", "engine", "monitor", "commander", "simulator", "database", "extra"
]
# What RestartServices accepts (RESTARTABLE_CATEGORIES).
RestartableCategory = Literal["vehicle", "engine", "monitor"]


# --- models ----------------------------------------------------------------


class StatusResponse(BaseModel):
    reachable: bool
    ok: bool = True
    configured: bool | None = None
    settings: dict[str, Any] = {}
    config_hash: str | None = None
    error: str | None = None


# Response models take config-derived values as plain dicts/strings rather
# than the validated request models below: a daemon's config may hold
# values the GCS would never write (runtime = "podman"), and reading them
# must not fail.
class InstanceModel(BaseModel):
    name: str
    category: str
    plugin_id: str
    runtime: str | None
    source: dict[str, Any] | None
    # The whole config entry (the form model's section shape), for the
    # Services tab's read-only config view.
    section: dict[str, Any]
    # From the daemon's ListServices; None when it can't say (an older
    # daemon without the RPC, or the call failed).
    running: bool | None = None
    uptime_s: float | None = None
    # Whether RestartServices takes it; the rest restart through Configure.
    restartable: bool = False


class PluginsResponse(BaseModel):
    reachable: bool
    ok: bool = True
    instances: list[InstanceModel] = []
    error: str | None = None


class InstanceRef(BaseModel):
    name: str = Field(max_length=NAME_MAX_LENGTH, pattern=NAME_PATTERN)
    category: RestartableCategory


class RestartBody(BaseModel):
    address: str
    instances: list[InstanceRef] = Field(min_length=1)


class DaemonAddressBody(BaseModel):
    address: str


class SimpleResponse(BaseModel):
    reachable: bool
    ok: bool = True
    error: str | None = None


# Request models for config edits. Unlike the response models these
# validate: the GCS only ever writes known runtimes and source kinds.
class SourceModel(BaseModel):
    kind: Literal["repo", "image"]
    url: str = Field(min_length=1)
    tag: str = ""


class PluginModel(BaseModel):
    # Empty is allowed when a source is given (eagled can name the plugin
    # after its URL); SectionModel requires one or the other.
    id: str = Field(
        default="",
        max_length=NAME_MAX_LENGTH,
        pattern=r"^(|[A-Za-z0-9][A-Za-z0-9._-]*)$",
    )
    runtime: Literal["process", "sandbox", "container"] | None = None
    source: SourceModel | None = None
    args: dict[str, Any] = {}
    extra: dict[str, Any] = {}

    @model_validator(mode="after")
    def _image_needs_container(self):
        if (
            self.source is not None
            and self.source.kind == "image"
            and self.runtime != "container"
        ):
            raise ValueError("an image source requires the container runtime")
        return self


def _find_nulls(value: Any, path: str) -> str | None:
    """Dotted path of the first None inside `value`, or None. TOML has no
    null, so tomlkit can't serialize one; rejecting it here keeps such a
    request a 422 instead of a 500 mid-edit."""
    if value is None:
        return path
    if isinstance(value, dict):
        for key, item in value.items():
            found = _find_nulls(item, f"{path}.{key}" if path else str(key))
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _find_nulls(item, f"{path}[{index}]")
            if found is not None:
                return found
    return None


class SectionModel(BaseModel):
    name: str = Field(max_length=NAME_MAX_LENGTH, pattern=NAME_PATTERN)
    plugin: PluginModel
    instance_fields: dict[str, Any] = {}

    @model_validator(mode="after")
    def _checks(self):
        if not self.plugin.id and self.plugin.source is None:
            raise ValueError(f"{self.name}: give a plugin ID or a source")
        clash = RESERVED_INSTANCE_KEYS & self.instance_fields.keys()
        if clash:
            raise ValueError(f"instance_fields can't set {sorted(clash)}")
        clash = MANAGED_PLUGIN_KEYS & self.plugin.extra.keys()
        if clash:
            raise ValueError(f"plugin.extra can't set {sorted(clash)}")
        for label, value in (
            ("plugin.args", self.plugin.args),
            ("plugin.extra", self.plugin.extra),
            ("instance_fields", self.instance_fields),
        ):
            path = _find_nulls(value, label)
            if path is not None:
                raise ValueError(f"null values can't be written to TOML: {path}")
        return self


Port = Field(default=None, ge=1, le=65535)


class SettingsModel(BaseModel):
    """Daemon-wide settings; None leaves the key out of the config."""

    model_config = ConfigDict(extra="forbid")

    hostname: str | None = Field(default=None, min_length=1)
    vehicle_port_base: int | None = Port
    gabriel_port: int | None = Port
    swarm_controller_port: int | None = Port
    headless: bool | None = None
    auto_run: bool | None = None
    auto_install: bool | None = None


class FormModel(BaseModel):
    settings: SettingsModel = SettingsModel()
    instances: dict[Category, list[SectionModel]] = {}

    @model_validator(mode="after")
    def _unique_names(self):
        for category, sections in self.instances.items():
            names = [s.name for s in sections]
            duplicates = sorted({n for n in names if names.count(n) > 1})
            if duplicates:
                raise ValueError(f"duplicate {category} names: {', '.join(duplicates)}")
        return self


def _exactly_one(form, raw_toml) -> None:
    if (form is None) == (raw_toml is None):
        raise ValueError("send exactly one of form and raw_toml")


class ConfigResponse(BaseModel):
    reachable: bool
    ok: bool = True
    config_hash: str | None = None
    raw_toml: str | None = None
    # None when the daemon's config can't be shown as a form (not valid
    # TOML, or the wrong shape); raw_toml is still returned for repair.
    form: dict[str, Any] | None = None
    error: str | None = None


class PutConfigBody(BaseModel):
    address: str
    config_hash: str
    form: FormModel | None = None
    raw_toml: str | None = None

    @model_validator(mode="after")
    def _one_form(self):
        _exactly_one(self.form, self.raw_toml)
        return self


class PutConfigResponse(BaseModel):
    reachable: bool
    ok: bool = True
    conflict: bool = False
    config_hash: str | None = None
    error: str | None = None


class ConvertBody(BaseModel):
    to: Literal["raw", "form"]
    # to=raw: the form is merged into base_toml (the raw text the form was
    # made from), so comments and keys the form doesn't show survive.
    form: FormModel | None = None
    base_toml: str = ""
    raw_toml: str | None = None

    @model_validator(mode="after")
    def _input_for_direction(self):
        if self.to == "raw" and self.form is None:
            raise ValueError("to=raw needs a form")
        if self.to == "form" and self.raw_toml is None:
            raise ValueError("to=form needs raw_toml")
        return self


class ConvertResponse(BaseModel):
    form: dict[str, Any] | None = None
    raw_toml: str | None = None


class DiscoveredDaemonModel(BaseModel):
    name: str
    address: str
    online: bool


class DiscoveredDaemonsResponse(BaseModel):
    daemons: list[DiscoveredDaemonModel] = []


# --- helpers ---------------------------------------------------------------


def _failure(model: type[BaseModel], e: BackendFailure, prefix: str = "", **fields):
    return model(
        reachable=not isinstance(e, DaemonUnreachable),
        ok=False,
        error=prefix + str(e),
        **fields,
    )


def _unprocessable(
    message: str, line: int | None = None, column: int | None = None
) -> HTTPException:
    return HTTPException(
        status_code=422, detail={"message": message, "line": line, "column": column}
    )


def _daemon_doc(text: str):
    """Parses the daemon's config. A config the daemon holds that isn't
    valid TOML is the daemon's problem, not the request's, so it surfaces as
    ok: false rather than a 422."""
    try:
        doc = daemon_config.parse(text)
    except daemon_config.ConfigError as e:
        raise DaemonError(f"daemon config is not valid TOML: {e.message}") from e
    try:
        daemon_config.validate(doc)
    except daemon_config.ConfigError as e:
        raise DaemonError(f"daemon config has an unexpected shape: {e.message}") from e
    return doc


def _request_doc(text: str, label: str = ""):
    """Parses TOML the client sent; any problem with it is a 422."""
    try:
        doc = daemon_config.parse(text)
        daemon_config.validate(doc)
    except daemon_config.ConfigError as e:
        raise _unprocessable(label + e.message, e.line, e.column) from e
    return doc


def _merge(base_doc, form: FormModel) -> str:
    try:
        daemon_config.apply_form(base_doc, form.model_dump())
    except daemon_config.ConfigError as e:
        raise _unprocessable(e.message) from e
    return daemon_config.dumps(base_doc)


def _form_of(doc) -> dict:
    """The document as a form, validated as strictly as an incoming one, so
    a config the form can't faithfully round-trip is refused up front
    rather than at save time."""
    form = daemon_config.to_form(doc)
    try:
        FormModel.model_validate(form)
    except ValidationError as e:
        raise daemon_config.ConfigError(
            "can't be edited as a form (use Raw TOML): "
            + "; ".join(err["msg"] for err in e.errors())
        ) from e
    return form


# --- read routes -----------------------------------------------------------


@router.get("/status")
async def get_status(address: str) -> StatusResponse:
    try:
        async with open_backend(address) as backend:
            text = await backend.get_configuration()
        doc = _daemon_doc(text)
    except BackendFailure as e:
        return _failure(StatusResponse, e)
    return StatusResponse(
        reachable=True,
        configured=bool(text.strip()),
        settings=daemon_config.daemon_settings(doc),
        config_hash=daemon_config.config_hash(text),
    )


@router.get("/plugins")
async def get_plugins(address: str) -> PluginsResponse:
    """The daemon's services, as listed in its config, with each one's run
    state from ListServices. The config is the list; a run state that can't
    be read leaves the list intact and says why."""
    states: dict[tuple[str, str], ServiceState] | None = None
    state_error: str | None = None
    try:
        async with open_backend(address) as backend:
            text = await backend.get_configuration()
            try:
                states = {
                    (s.name, s.category): s for s in await backend.list_services()
                }
            except NotSupported:
                pass
            except BackendFailure as e:
                state_error = f"Service status unavailable: {e}"
        doc = _daemon_doc(text)
    except BackendFailure as e:
        return _failure(PluginsResponse, e)
    instances = []
    for category, section in daemon_config.list_sections(doc):
        state = None if states is None else states.get((section["name"], category))
        instances.append(
            InstanceModel(
                name=section["name"],
                category=category,
                plugin_id=section["plugin"]["id"],
                runtime=section["plugin"]["runtime"],
                source=section["plugin"]["source"],
                section=section,
                # Configured but not reported: the daemon isn't running it.
                running=None if states is None else bool(state and state.running),
                uptime_s=state.uptime_s if state else None,
                restartable=category in RESTARTABLE_CATEGORIES,
            )
        )
    return PluginsResponse(
        reachable=True, ok=state_error is None, error=state_error, instances=instances
    )


@router.get("/config")
async def get_config(address: str) -> ConfigResponse:
    try:
        async with open_backend(address) as backend:
            text = await backend.get_configuration()
    except BackendFailure as e:
        return _failure(ConfigResponse, e)
    response = ConfigResponse(
        reachable=True, config_hash=daemon_config.config_hash(text), raw_toml=text
    )
    try:
        response.form = _form_of(_daemon_doc(text))
    except DaemonError as e:
        response.ok, response.error = False, str(e)
    except daemon_config.ConfigError as e:
        response.ok, response.error = False, e.message
    return response


# --- commands --------------------------------------------------------------


@router.post("/plugins/restart")
async def restart_plugins(body: RestartBody) -> SimpleResponse:
    refs = [ServiceRef(i.name, i.category) for i in body.instances]
    try:
        async with open_backend(body.address) as backend:
            await backend.restart_services(refs)
    except BackendFailure as e:
        return _failure(SimpleResponse, e)
    return SimpleResponse(reachable=True)


@router.put("/config")
async def put_config(body: PutConfigBody) -> PutConfigResponse:
    """Replaces the daemon's whole config, which restarts the daemon and
    every service it runs."""
    if body.raw_toml is not None:
        _request_doc(body.raw_toml)
    try:
        async with open_backend(body.address) as backend:
            current = await backend.get_configuration()
            if daemon_config.config_hash(current) != body.config_hash:
                return PutConfigResponse(
                    reachable=True, ok=False, conflict=True, error=CONFLICT_MESSAGE
                )
            if body.raw_toml is not None:
                new_text = body.raw_toml
            else:
                # A form is merged into the daemon's current document, which
                # must therefore be readable; a raw save can repair one that
                # isn't.
                new_text = _merge(_daemon_doc(current), body.form)
            await backend.configure(new_text)
    except BackendFailure as e:
        return _failure(PutConfigResponse, e)
    return PutConfigResponse(
        reachable=True, config_hash=daemon_config.config_hash(new_text)
    )


@router.post("/config/convert")
async def convert_config(body: ConvertBody) -> ConvertResponse:
    """Switches the Configure dialog between its Form and Raw TOML views."""
    if body.to == "raw":
        return ConvertResponse(
            raw_toml=_merge(_request_doc(body.base_toml, "base config: "), body.form)
        )
    try:
        form = _form_of(_request_doc(body.raw_toml))
    except daemon_config.ConfigError as e:
        raise _unprocessable(e.message) from e
    return ConvertResponse(form=form)


@router.post("/reset-config")
async def reset_config(body: DaemonAddressBody) -> SimpleResponse:
    try:
        async with open_backend(body.address) as backend:
            await backend.reset_configuration()
    except BackendFailure as e:
        return _failure(SimpleResponse, e)
    return SimpleResponse(reachable=True)


# --- discovery -----------------------------------------------------------------


async def _run_tailscale_status() -> dict | None:
    """Runs `tailscale status --json` on this host and returns the parsed
    status, or None if it can't be run (no `tailscale` binary, tailscaled
    not running, or malformed output). Discovery is best-effort: a GCS host
    that isn't tailnet-joined just sees no discovered daemons, not an
    error."""
    tailscale = shutil.which("tailscale")
    if tailscale is None:
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            tailscale,
            "status",
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        return json.loads(stdout)
    except (OSError, json.JSONDecodeError):
        return None


def _discovered_daemons_from_status(status: dict) -> list[DiscoveredDaemonModel]:
    daemons = []
    for peer in status.get("Peer", {}).values():
        if DAEMON_TAILSCALE_TAG not in (peer.get("Tags") or []):
            continue
        dns_name = (peer.get("DNSName") or "").rstrip(".")
        if not dns_name:
            continue
        daemons.append(
            DiscoveredDaemonModel(
                name=peer.get("HostName") or dns_name,
                address=f"{dns_name}:{DEFAULT_CONTROL_PORT}",
                online=bool(peer.get("Online")),
            )
        )
    daemons.sort(key=lambda d: d.name)
    return daemons


@router.get("/discovered")
async def get_discovered_daemons() -> DiscoveredDaemonsResponse:
    status = await _run_tailscale_status()
    daemons = [] if status is None else _discovered_daemons_from_status(status)
    if mock_enabled():
        daemons += [
            DiscoveredDaemonModel(name=name, address=address, online=True)
            for name, address in MOCK_DISCOVERED
        ]
    return DiscoveredDaemonsResponse(daemons=daemons)
