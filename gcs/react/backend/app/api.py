import asyncio
import base64
import binascii
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2
import grpc
import numpy as np
import redis
import requests
import steeleagle_sdk
import toml
from colorhash import ColorHash
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from lark import Lark, Token, Transformer, UnexpectedInput, v_args
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    ValidationError,
)
from pydantic_extra_types.coordinate import Latitude, Longitude
from rich.logging import RichHandler
from steeleagle_sdk.dsl.compiler.ir import ActionIR, EventIR, MissionIR
from steeleagle_sdk.dsl.compiler.loader import load_all as _dsl_load_all
from steeleagle_sdk.dsl.compiler.registry import (
    _ACTIONS,
    _EVENTS,
    get_action,
    get_event,
)
from steeleagle_protocol.v1.services.dslcompiler import (
    dslcompiler_pb2_grpc,
)
from steeleagle_protocol.v1.services.swarm import swarm_pb2_grpc

from app.dslcompiler_client import DslCompilerClient
from app.swarm_client import SwarmClient, VehicleResult

IDENTITY_MD = (("identity", "server"),)
FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("rich")

backend_key = os.getenv("BACKEND")


class Start(BaseModel):
    vehicles: list[str]


class Upload(BaseModel):
    binary: str  # base64-encoded compiled Go mission binary
    map: str  # base64-encoded map data (KML or GeoJSON, format-agnostic)
    vehicles: list[str]


class Joystick(BaseModel):
    xvel: float = Field(default=0.0)
    yvel: float = Field(default=0.0)
    zvel: float = Field(default=0.0)
    angularvel: float = Field(default=0.0)
    duration: int = Field(default=1)
    vehicles: list[str]


class GimbalPose(BaseModel):
    pitch: float = Field(default=0.0)
    yaw: float = Field(default=0.0)
    roll: float = Field(default=0.0)
    vehicles: list[str]


class Command(BaseModel):
    takeoff: NonNegativeInt | None = None
    land: bool | None = None
    rth: bool | None = None
    hold: bool | None = None
    stop_mission: bool | None = None
    arm: bool | None = None
    vehicles: list[str]


class Location(BaseModel):
    lat: Latitude
    long: Longitude
    alt: NonNegativeFloat


class Velocity(BaseModel):
    x_vel: float
    y_vel: float
    z_vel: float
    angular_vel: float


class Vehicle(BaseModel):
    name: str
    model: str | None = None
    battery: NonNegativeInt
    sats: NonNegativeInt
    mag: NonNegativeInt
    last_updated: float
    type: str = Field(default="UAV")
    selected: bool = Field(default=False)
    home: Location | None = None
    current: Location
    bearing: NonNegativeFloat
    velocity: Velocity | None = None


class Detection(BaseModel):
    id: str
    cls: str
    confidence: NonNegativeFloat
    longitude: Longitude
    latitude: Latitude
    x_min: NonNegativeFloat
    y_min: NonNegativeFloat
    x_max: NonNegativeFloat
    y_max: NonNegativeFloat
    link: str | None = None


class BackendConnection(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    grpc_channel: grpc.aio.Channel
    swarm_client: SwarmClient
    redis_connection: redis.Redis
    webserver: str
    show_detections: bool


class ShowDetectionsConfig(BaseModel):
    show_detections: bool


class ConnectionManager:
    """Manages WebSocket connections for broadcasting imagery to multiple websocket clients"""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, vehicle: str):
        await websocket.accept()
        async with self.lock:
            if vehicle not in self.active_connections:
                self.active_connections[vehicle] = []
            self.active_connections[vehicle].append(websocket)
        logger.info(
            f"{websocket.client.host} connected to vehicle '{vehicle}' ({len(self.active_connections[vehicle])} clients)"
        )

    async def disconnect(self, websocket: WebSocket, vehicle: str):
        async with self.lock:
            if vehicle in self.active_connections:
                if websocket in self.active_connections[vehicle]:
                    self.active_connections[vehicle].remove(websocket)
                    logger.info(
                        f"{websocket.client.host} disconnected from vehicle '{vehicle}'  ({len(self.active_connections[vehicle])} clients)"
                    )

                # Clean up empty lists
                if not self.active_connections[vehicle]:
                    del self.active_connections[vehicle]

    async def broadcast(self, vehicle: str, message: str):
        if vehicle not in self.active_connections:
            return

        # Create a copy of the connections list to avoid issues with concurrent modifications
        connections = self.active_connections[vehicle].copy()
        disconnected = []

        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        if disconnected:
            async with self.lock:
                for connection in disconnected:
                    if (
                        vehicle in self.active_connections
                        and connection in self.active_connections[vehicle]
                    ):
                        self.active_connections[vehicle].remove(connection)

                # Clean up empty lists
                if (
                    vehicle in self.active_connections
                    and not self.active_connections[vehicle]
                ):
                    del self.active_connections[vehicle]

    def get_client_count(self, vehicle: str) -> int:
        return len(self.active_connections.get(vehicle, []))


with open("config.toml") as file:
    cfg = toml.load(file)

backend_connections: dict[str, BackendConnection] = {}
connection_manager = ConnectionManager()
dslcompiler_channel: grpc.aio.Channel | None = None
dslcompiler_client: DslCompilerClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    for b in cfg["backend"]:
        backend = cfg["backend"][b]
        swarm_controller_channel = grpc.aio.insecure_channel(
            backend["swarm-controller"]
        )
        swarm_stub = swarm_pb2_grpc.SwarmServiceStub(swarm_controller_channel)
        swarm_client = SwarmClient(swarm_stub)
        logger.info(
            f" **{b}** Opened SwarmService stub at GRPC endpoint: {backend['swarm-controller']}"
        )
        red = redis.Redis(
            host=backend["redis_host"],
            port=backend["redis_port"],
            username=backend["redis_username"],
            password=backend["redis_password"],
            decode_responses=True,
        )
        logger.info(
            f" **{b}** Connected to redis at : {backend['redis_host']}:{backend['redis_port']}"
        )
        webserver = backend["webserver"]
        bc = BackendConnection(
            grpc_channel=swarm_controller_channel,
            swarm_client=swarm_client,
            redis_connection=red,
            webserver=webserver,
            show_detections=True,
        )
        backend_connections[b] = bc
    if backend_key is not None:
        logger.info(f"Using backend '{backend_key}' based on BACKEND env var")
    else:
        logger.info(f"Using default backend '{list(backend_connections.keys())[0]}'")

    global dslcompiler_channel, dslcompiler_client
    dslcompiler_channel = grpc.aio.insecure_channel(cfg["dslcompiler"]["controller"])
    dslcompiler_stub = dslcompiler_pb2_grpc.DslCompilerServiceStub(dslcompiler_channel)
    dslcompiler_client = DslCompilerClient(dslcompiler_stub)
    logger.info(
        f"Opened DslCompilerService stub at GRPC endpoint: {cfg['dslcompiler']['controller']}"
    )

    _dsl_load_all()

    global _dsl_parser
    try:
        _dsl_parser = Lark.open(
            str(_GRAMMAR_PATH), parser="earley", start="start", ambiguity="resolve"
        )
        logger.info(f"DSL parser initialized from {_GRAMMAR_PATH}")
    except Exception as exc:
        logger.warning(f"DSL parser init failed: {exc}")

    yield
    # Cleanup
    for _name, conn in backend_connections.items():
        await conn.grpc_channel.close()
        conn.redis_connection.close()
    if dslcompiler_channel is not None:
        await dslcompiler_channel.close()


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg["cors"]["origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _current_connection() -> BackendConnection:
    if backend_key is None:
        return backend_connections[list(backend_connections)[0]]
    return backend_connections[backend_key]


def _current_dslcompiler_client() -> DslCompilerClient:
    if dslcompiler_client is None:
        raise HTTPException(
            status_code=503, detail="dslcompiler client not initialized"
        )
    return dslcompiler_client


async def _remote_imagery_broadcaster(vehicle: str):
    """
    Background task for remote imagery fetching and broadcasting
    """
    logger.debug(f"Starting remote imagery broadcaster for '{vehicle}'")
    if backend_key is None:
        conn = backend_connections[list(backend_connections)[0]]
    else:
        conn = backend_connections[backend_key]

    while connection_manager.get_client_count(f"remote_{vehicle}") > 0:
        try:
            url = f"{conn.webserver}/raw/{vehicle}/latest.jpg?t={time.time()}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                img_bytes = response.content
                if conn.show_detections:
                    nparr = np.frombuffer(img_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    maybe_add_bboxes(vehicle, img)
                    _, img_bytes = cv2.imencode(
                        ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90]
                    )
                base64_image = base64.b64encode(img_bytes).decode("ascii")
                await connection_manager.broadcast(f"remote_{vehicle}", base64_image)
            await asyncio.sleep(0.1)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching remote image for {vehicle}: {e}")
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in remote imagery broadcaster for {vehicle}: {e}")
            await asyncio.sleep(0.5)

    logger.debug(f"Stopping remote imagery broadcaster for '{vehicle}' (no clients)")


def get_latest_detections(vehicle_id):
    if backend_key is None:
        conn = backend_connections[list(backend_connections)[0]].redis_connection
    else:
        conn = backend_connections[backend_key].redis_connection
    red = conn

    key_obj = f"latest-detection:{vehicle_id}"
    key_aruco = f"aruco-detection:{vehicle_id}"
    pipe = red.pipeline()
    pipe.lrange(key_obj, 0, -1)
    pipe.lrange(key_aruco, 0, -1)
    raw_obj, raw_aruco = pipe.execute()

    raw = raw_obj or []  # + (raw_aruco or [])

    if not raw:
        return []

    detections = []
    for d in raw:
        try:
            detection = json.loads(d)
            detections.append(detection)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(e)
            return []
    return detections


def maybe_add_bboxes(vehicle_id, img):
    detections = get_latest_detections(vehicle_id)
    if len(detections) == 0:
        return
    h, w = img.shape[:2]

    for det in detections:
        try:
            y_min_f, x_min_f, y_max_f, x_max_f = det["box"]
        except (KeyError, ValueError, TypeError) as e:
            logger.error(e)
            continue

        # Convert fractional coords → pixel coords
        x1 = int(x_min_f * w)
        y1 = int(y_min_f * h)
        x2 = int(x_max_f * w)
        y2 = int(y_max_f * h)

        cls = det.get("class", "unknown")
        score = det.get("score", 0.0)
        label = f"{cls} {score:.2f}"
        color = ColorHash(cls).rgb

        # Bounding box
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness=2)

        # Label background
        (text_w, text_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        label_y1 = max(y1 - text_h - baseline - 4, 0)
        cv2.rectangle(
            img,
            (x1, label_y1),
            (x1 + text_w + 4, y1),
            color,
            thickness=cv2.FILLED,
        )

        # Label text
        cv2.putText(
            img,
            label,
            (x1 + 2, y1 - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            thickness=1,
            lineType=cv2.LINE_AA,
        )


def add_watermark(img):
    ts = time.strftime("%H:%M:%S")
    cv2.putText(
        img, f"{ts}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 5, cv2.LINE_AA
    )
    cv2.putText(
        img,
        f"{ts}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


# API Routes
@app.get("/api/remote/backends")
async def get_backends() -> list[str]:
    return backend_connections.keys()


@app.get("/api/remote/objects")
async def get_objects() -> list[Detection]:
    data = []
    if backend_key is None:
        conn = backend_connections[list(backend_connections)[0]].redis_connection
    else:
        conn = backend_connections[backend_key].redis_connection
    red = conn
    for obj in red.zrange("detections", 0, -1):
        if len(red.keys(f"objects:{obj}")) > 0:
            fields = red.hgetall(f"objects:{obj}")
            data.append(
                Detection(
                    id=obj,
                    cls=fields.get("cls", "unknown"),
                    confidence=float(fields.get("confidence", 0.0)),
                    longitude=Longitude(float(fields.get("longitude", 0.0))),
                    latitude=Latitude(float(fields.get("latitude", 0.0))),
                    x_min=NonNegativeFloat(float(fields.get("x_min", 0.0))),
                    y_min=NonNegativeFloat(float(fields.get("y_min", 0.0))),
                    x_max=NonNegativeFloat(float(fields.get("x_max", 0.0))),
                    y_max=NonNegativeFloat(float(fields.get("y_max", 0.0))),
                    link=fields.get("link", ""),
                )
            )

    return data


@app.get("/api/remote/vehicles")
async def get_vehicles() -> list[Vehicle]:
    data = []
    current = Location(lat=42, long=-79, alt=0)
    bearing = 0
    if backend_key is None:
        conn = backend_connections[list(backend_connections)[0]].redis_connection
    else:
        conn = backend_connections[backend_key].redis_connection
    red = conn
    for k in red.keys("vehicle:*"):
        fields = red.hgetall(k)
        drone_name = k.split(":")[-1]
        fields["name"] = drone_name
        try:
            home_loc = Location(
                lat=fields["position_info.home_lat"],
                long=fields["position_info.home_long"],
                alt=fields["position_info.home_alt"],
            )
            if red.exists(f"telemetry:{drone_name}"):
                telem = red.xrevrange(f"telemetry:{drone_name}", "+", "-", 1)
                for item in telem:
                    t = item[1]
                    current = Location(
                        lat=t["latitude"],
                        long=t["longitude"],
                        alt=max(0, float(t["rel_altitude"])),
                    )
                    bearing = t["bearing"]
                    vel = Velocity(
                        x_vel=t["v_body_forward"],
                        y_vel=t["v_body_lateral"],
                        z_vel=t["v_body_altitude"],
                        angular_vel=t["v_body_angular"],
                    )
            data.append(
                Vehicle(
                    name=fields["name"],
                    model=fields["model"],
                    battery=t["battery"],
                    sats=t["sats"],
                    mag=fields["mag"],
                    last_updated=round(time.time() - float(fields["last_seen"]), 2),
                    home=home_loc,
                    current=current,
                    bearing=bearing,
                    velocity=vel,
                )
            )
        except KeyError as e:
            logger.error(
                f"Vehicle '{drone_name}' is missing required field {e} in Redis"
            )
            raise HTTPException(
                status_code=502,
                detail=f"Vehicle '{drone_name}' is missing required field {e}",
            ) from e

    return data


@app.post("/api/imagery/show_detections")
async def show_detections(config: ShowDetectionsConfig):
    for backend in backend_connections.values():
        backend.show_detections = config.show_detections
    return {"status": "updated", "show_detections": config.show_detections}


@app.websocket("/ws/imagery/remote/{vehicle}")
async def remote_websocket_endpoint(websocket: WebSocket, vehicle: str):
    if vehicle == "":
        await websocket.close(code=1008, reason="Vehicle name required")
        return

    vehicle_key = f"remote_{vehicle}"
    await connection_manager.connect(websocket, vehicle_key)

    # Start broadcaster task if this is the first client for this vehicle
    if connection_manager.get_client_count(vehicle_key) == 1:
        asyncio.create_task(_remote_imagery_broadcaster(vehicle))

    try:
        # Keep the connection alive and handle any incoming messages
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from /ws/imagery/remote/{vehicle}")
    except Exception as e:
        logger.error(f"WebSocket error for remote vehicle '{vehicle}': {e}")
    finally:
        await connection_manager.disconnect(websocket, vehicle_key)


@app.post("/api/gimbal")
async def set_gimbal_pose(req: GimbalPose) -> JSONResponse:
    conn = _current_connection()
    conn.grpc_channel.get_state(try_to_connect=True)
    try:
        results = await conn.swarm_client.set_gimbal_pose(
            req.vehicles, pitch=req.pitch, yaw=req.yaw, roll=req.roll
        )
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return JSONResponse(
        status_code=200, content={"results": [r.model_dump() for r in results]}
    )


@app.post("/api/start")
async def start(req: Start) -> JSONResponse:
    conn = _current_connection()
    conn.grpc_channel.get_state(try_to_connect=True)
    try:
        results = await conn.swarm_client.start_mission(req.vehicles)
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return JSONResponse(
        status_code=200, content={"results": [r.model_dump() for r in results]}
    )


@app.post("/api/upload")
async def upload(req: Upload) -> JSONResponse:
    conn = _current_connection()
    conn.grpc_channel.get_state(try_to_connect=True)
    try:
        mission_binary = base64.b64decode(req.binary)
        map_data = base64.b64decode(req.map)
    except binascii.Error as e:
        raise HTTPException(status_code=400, detail="Invalid base64 payload") from e
    try:
        results = await conn.swarm_client.upload_mission(
            req.vehicles, mission_binary=mission_binary, map_data=map_data
        )
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return JSONResponse(
        status_code=200, content={"results": [r.model_dump() for r in results]}
    )


@app.post("/api/joystick")
async def joystick(req: Joystick) -> JSONResponse:
    conn = _current_connection()
    conn.grpc_channel.get_state(try_to_connect=True)
    logger.info(f"Joystick: {req}")
    try:
        results = await conn.swarm_client.set_velocity(
            req.vehicles,
            x_vel=req.xvel,
            y_vel=req.yvel,
            z_vel=req.zvel,
            angular_vel=req.angularvel,
        )
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return JSONResponse(
        status_code=200, content={"results": [r.model_dump() for r in results]}
    )


@app.post("/api/command")
async def command(req: Command) -> JSONResponse:
    logger.info(f"Sending command to {req.vehicles}...")
    conn = _current_connection()
    conn.grpc_channel.get_state(try_to_connect=True)
    results: list[VehicleResult] = []
    try:
        if req.takeoff is not None:
            results = await conn.swarm_client.take_off(
                req.vehicles, altitude=req.takeoff
            )
        elif req.land:
            results = await conn.swarm_client.land(req.vehicles)
        elif req.rth:
            results = await conn.swarm_client.return_to_home(req.vehicles)
        elif req.hold:
            hold_results = await conn.swarm_client.hold(req.vehicles)
            stop_results = await conn.swarm_client.stop_mission(req.vehicles)
            results = hold_results + stop_results
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return JSONResponse(
        status_code=200, content={"results": [r.model_dump() for r in results]}
    )


def _resolve_ref(prop: dict, defs: dict) -> dict:
    """Follow a single $ref pointer in a JSON Schema fragment."""
    if "$ref" in prop:
        ref_name = prop["$ref"].split("/")[-1]
        return defs.get(ref_name, prop)
    return prop


def _unwrap_anyof(prop: dict) -> dict:
    """Unwrap anyOf by selecting the best non-null branch.

    - If exactly one non-null branch exists (Optional pattern), return it.
    - If multiple non-null branches exist, prefer a scalar type branch
      (string, number, integer, boolean) over array/object.
    """
    if "anyOf" in prop:
        non_null = [t for t in prop["anyOf"] if t.get("type") != "null"]
        if len(non_null) == 1:
            return non_null[0]
        if len(non_null) > 1:
            _SCALAR_TYPES = ("string", "number", "integer", "boolean")
            scalar = next((t for t in non_null if t.get("type") in _SCALAR_TYPES), None)
            if scalar is not None:
                return scalar
    return prop


def _extract_fields_from_schema(schema: dict, defs: dict, depth: int = 0) -> list[dict]:
    """Extract fields from a raw JSON Schema dict. Recurses into $defs for nested object types."""
    properties = schema.get("properties", {})
    required_set = set(schema.get("required", []))
    fields = []
    for name, raw_prop in properties.items():
        prop = _resolve_ref(raw_prop, defs)
        prop = _unwrap_anyof(prop)
        prop = _resolve_ref(prop, defs)

        field_type = prop.get("type", "object")
        if field_type not in ("string", "number", "integer", "boolean", "array"):
            field_type = "object"

        entry: dict = {
            "name": name,
            "type": field_type,
            "required": name in required_set,
            "description": raw_prop.get("description", prop.get("description", "")),
        }
        if "default" in raw_prop:
            entry["default"] = raw_prop["default"]

        if field_type == "object":
            ref_raw = (
                raw_prop
                if "$ref" in raw_prop
                else (next((t for t in raw_prop.get("anyOf", []) if "$ref" in t), {}))
            )
            ref_name = ref_raw.get("$ref", "").split("/")[-1]
            if ref_name:
                entry["object_type"] = ref_name
                if depth < 2:
                    nested_schema = defs.get(ref_name, {})
                    if nested_schema:
                        entry["nested_fields"] = _extract_fields_from_schema(
                            nested_schema, defs, depth + 1
                        )

        fields.append(entry)
    return fields


def _extract_fields(cls) -> list[dict]:
    """Return a flat field list from a Pydantic model class."""
    schema = cls.model_json_schema()
    defs = schema.get("$defs", {})
    return _extract_fields_from_schema(schema, defs, depth=0)


_GRAMMAR_PATH = Path(steeleagle_sdk.__path__[0]) / "dsl" / "grammar" / "dronedsl.lark"
_dsl_parser: Lark | None = None


@v_args(inline=True)
class _RawDslExtractor(Transformer):
    """
    Lark transformer that extracts the structural skeleton of a DSL file as plain
    Python dicts without resolving types or running the validator.
    Data-section references are expanded to their attribute dicts.
    """

    def __init__(self):
        super().__init__()
        self._data: dict[str, dict] = {}
        self._actions: list[dict] = []
        self._events: list[dict] = []
        self._start_id: str | None = None
        self._during: dict[str, dict[str, str]] = {}

    # ---- helpers ----

    def _pairs_to_dict(self, items) -> dict:
        if items is None:
            return {}
        return {k: v for k, v in items if isinstance(k, str)}

    def _resolve_val(self, v: Any) -> Any:
        """Expand a Data-section ID reference to its attrs dict; pass everything else through."""
        if isinstance(v, str) and v in self._data:
            return dict(self._data[v]["attrs"])
        return v

    def _resolve_attrs(self, attrs: dict) -> dict:
        return {k: self._resolve_val(v) for k, v in attrs.items()}

    # ---- grammar rules ----

    def datum_body(self, *items):
        return [it for it in items if isinstance(it, tuple)]

    def datum_decl(self, type_name: Token, datum_id: Token, attrs=None):
        did = str(datum_id)
        self._data[did] = {
            "type_name": str(type_name),
            "attrs": self._pairs_to_dict(attrs or []),
        }

    def action_body(self, *items):
        return [it for it in items if isinstance(it, tuple)]

    def action_decl(self, type_name: Token, action_id: Token, attrs=None):
        self._actions.append(
            {
                "type_name": str(type_name),
                "instance_id": str(action_id),
                "params": self._resolve_attrs(self._pairs_to_dict(attrs or [])),
            }
        )

    def event_body(self, *items):
        return [it for it in items if isinstance(it, tuple)]

    def event_decl(self, type_name: Token, event_id: Token, attrs=None):
        self._events.append(
            {
                "type_name": str(type_name),
                "instance_id": str(event_id),
                "params": self._resolve_attrs(self._pairs_to_dict(attrs or [])),
            }
        )

    def mission_start(self, _kw: Token, action_id: Token, *_rest):
        self._start_id = str(action_id)

    def transition_rule(self, eid: Token, _arrow: Token, nxt_aid: Token, *_rest):
        return (str(eid), str(nxt_aid))

    def transition_body(self, *items):
        return [it for it in items if isinstance(it, tuple)]

    def during_block(self, _kw: Token, action_id: Token, *rest):
        aid = str(action_id)
        self._during.setdefault(aid, {})
        # last positional arg is the transition_body list; earlier args are tokens (COLON etc.)
        rules_list = next((r for r in rest if isinstance(r, list)), [])
        for eid, nxt in rules_list:
            self._during[aid][eid] = nxt

    def mission_block(self, *_):
        return None

    def attr(self, k: Token, _sep, v):
        return (str(k), v)

    def value(self, v):
        if isinstance(v, dict | list):
            return v
        if isinstance(v, Token):
            if v.type == "NUMBER":
                return float(str(v))
            if v.type == "NAME":
                return str(v)
            if v.type == "NONE":
                return None
        return v

    def array(self, *items):
        return [it for it in items if not isinstance(it, Token)]

    def datum_args(self, *items):
        return [it for it in items if not isinstance(it, Token)]

    def datum_inline(self, type_name: Token, *args):
        args_list = next((c for c in args if isinstance(c, list)), [])
        return {"__inline__": True, "type": str(type_name), "args": args_list}

    def start(self, *_children):
        edges = []
        for source, evmap in self._during.items():
            for eid, target in evmap.items():
                if target != "terminate":
                    edges.append({"source": source, "event_id": eid, "target": target})
        return {
            "nodes": self._actions,
            "events": self._events,
            "edges": edges,
            "start_id": self._start_id,
        }


class ParseDslRequest(BaseModel):
    dsl: str


@app.post("/api/parse_dsl")
async def parse_dsl(request: ParseDslRequest):
    global _dsl_parser
    if _dsl_parser is None:
        raise HTTPException(status_code=503, detail="DSL parser not initialized")
    try:
        tree = _dsl_parser.parse(request.dsl)
        result = _RawDslExtractor().transform(tree)
        return result
    except UnexpectedInput as exc:
        raise HTTPException(status_code=422, detail=f"Parse error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def build_schema_response() -> dict:
    """Pure function — safe to call from tests without the full app running."""
    result: dict = {"actions": {}, "events": {}}
    for _type_name, cls in _ACTIONS.items():
        display = cls.__name__  # original CamelCase name
        result["actions"][display] = {
            "description": (cls.__doc__ or "").strip().splitlines()[0]
            if cls.__doc__
            else "",
            "fields": _extract_fields(cls),
        }
    for _type_name, cls in _EVENTS.items():
        display = cls.__name__
        result["events"][display] = {
            "description": (cls.__doc__ or "").strip().splitlines()[0]
            if cls.__doc__
            else "",
            "fields": _extract_fields(cls),
        }
    if not result["actions"] and not result["events"]:
        raise HTTPException(
            status_code=500, detail="Schema registry is empty — DSL load failed"
        )
    return result


@app.get("/api/schema")
async def get_schema():
    return build_schema_response()


class CompileNode(BaseModel):
    instance_id: str
    type_name: str
    params: dict = {}


class CompileEvent(BaseModel):
    instance_id: str
    type_name: str
    params: dict = {}


class CompileEdge(BaseModel):
    source: str
    event_id: str
    target: str


class CompileRequest(BaseModel):
    nodes: list[CompileNode]
    events: list[CompileEvent]
    edges: list[CompileEdge]
    start_id: str


def compile_mission(request: CompileRequest) -> dict:
    """Pure function — safe to call from tests without the full app running."""
    _dsl_load_all()
    errors: list[dict] = []

    # Check for duplicate instance_ids
    seen_ids: set[str] = set()
    for node in request.nodes:
        if node.instance_id in seen_ids:
            errors.append(
                {
                    "node_id": node.instance_id,
                    "message": f"Duplicate node instance_id: '{node.instance_id}'",
                }
            )
        seen_ids.add(node.instance_id)
    seen_event_ids: set[str] = set()
    for ev in request.events:
        if ev.instance_id in seen_event_ids:
            errors.append(
                {
                    "node_id": ev.instance_id,
                    "message": f"Duplicate event instance_id: '{ev.instance_id}'",
                }
            )
        seen_event_ids.add(ev.instance_id)

    # Validate all type_names exist and params are valid
    for node in request.nodes:
        cls = get_action(node.type_name)
        if cls is None:
            errors.append(
                {
                    "node_id": node.instance_id,
                    "message": f"Unknown action type: {node.type_name}",
                }
            )
            continue
        try:
            cls(**node.params)
        except (ValidationError, TypeError) as exc:
            errors.append({"node_id": node.instance_id, "message": str(exc)})

    for ev in request.events:
        cls = get_event(ev.type_name)
        if cls is None:
            errors.append(
                {
                    "event_id": ev.instance_id,
                    "message": f"Unknown event type: {ev.type_name}",
                }
            )
            continue
        try:
            cls(**ev.params)
        except (ValidationError, TypeError) as exc:
            errors.append({"event_id": ev.instance_id, "message": str(exc)})

    # Validate start_id refers to a known node
    node_ids = {n.instance_id for n in request.nodes}
    if request.start_id not in node_ids:
        errors.append(
            {
                "node_id": request.start_id,
                "message": f"start_id '{request.start_id}' does not refer to any node",
            }
        )

    # Validate edge referential integrity
    event_ids = {ev.instance_id for ev in request.events} | {"done"}
    for edge in request.edges:
        if edge.source not in node_ids:
            errors.append(
                {
                    "node_id": edge.source,
                    "message": f"Edge source '{edge.source}' does not refer to any node",
                }
            )
        if edge.target not in node_ids:
            errors.append(
                {
                    "node_id": edge.target,
                    "message": f"Edge target '{edge.target}' does not refer to any node",
                }
            )
        if edge.event_id not in event_ids:
            errors.append(
                {
                    "node_id": edge.event_id,
                    "message": f"Edge event_id '{edge.event_id}' does not refer to any declared event",
                }
            )

    if errors:
        return {"errors": errors}

    # Build MissionIR
    actions = {
        n.instance_id: ActionIR(
            type_name=n.type_name,
            action_id=n.instance_id,
            attributes=n.params,
        )
        for n in request.nodes
    }
    events = {
        e.instance_id: EventIR(
            type_name=e.type_name,
            event_id=e.instance_id,
            attributes=e.params,
        )
        for e in request.events
    }

    transitions: dict[str, dict[str, str]] = {}
    for edge in request.edges:
        transitions.setdefault(edge.source, {})[edge.event_id] = edge.target

    mission_ir = MissionIR(
        actions=actions,
        events=events,
        data={},
        start_action_id=request.start_id,
        transitions=transitions,
    )
    return {"mission": asdict(mission_ir)}


@app.post("/api/compile")
async def compile_mission_route(request: CompileRequest) -> dict:
    return compile_mission(request)


# Serve Vite static files
app.mount("/", StaticFiles(directory="../prime/dist", html=True), name="react_app")
