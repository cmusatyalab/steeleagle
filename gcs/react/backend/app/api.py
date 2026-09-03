import asyncio
import base64
import binascii
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Literal

import cv2
import grpc
import numpy as np
import redis
import requests
import toml
from colorhash import ColorHash
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
)
from pydantic_extra_types.coordinate import Latitude, Longitude
from rich.logging import RichHandler
from steeleagle_protocol.v1.services.dslcompiler import (
    dslcompiler_pb2,
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
    dsl_cfg = cfg.get("dslcompiler")
    if dsl_cfg and dsl_cfg.get("controller"):
        dslcompiler_channel = grpc.aio.insecure_channel(dsl_cfg["controller"])
        dslcompiler_stub = dslcompiler_pb2_grpc.DslCompilerServiceStub(
            dslcompiler_channel
        )
        dslcompiler_client = DslCompilerClient(dslcompiler_stub)
        logger.info(
            f"Opened DslCompilerService stub at GRPC endpoint: {dsl_cfg['controller']}"
        )
    else:
        logger.warning(
            "no [dslcompiler] config section (or no 'controller' key) — "
            "FSM-builder routes will return 503 until config.toml is updated"
        )

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


def _field_value_to_python(fv: dslcompiler_pb2.FieldValue):
    which = fv.WhichOneof("value")
    if which == "float_value":
        return fv.float_value
    if which == "int_value":
        return fv.int_value
    if which == "string_value":
        return fv.string_value
    if which == "bool_value":
        return fv.bool_value
    if which == "ident_ref":
        return fv.ident_ref
    if which == "array_value":
        return [_field_value_to_python(e) for e in fv.array_value.elems]
    if which == "inline_value":
        return {k: _field_value_to_python(v) for k, v in fv.inline_value.args.items()}
    return None


def parse_dsl_response_to_dict(resp: dslcompiler_pb2.ParseDslResponse) -> dict:
    """Pure function -- translates a ParseDslResponse into the same
    {nodes, events, edges, start_id} shape PlanPage.jsx's loadFromParsed
    already consumes, with bare type_names and plain-JSON params (the
    reverse of _mission_graph_from_request). Raises HTTPException on a
    parse error so the route handler doesn't need its own error-shape
    logic."""
    if not resp.ok:
        raise HTTPException(
            status_code=422,
            detail="; ".join(e.message for e in resp.errors) or "DSL parse error",
        )
    mission = resp.mission
    return {
        "nodes": [
            {
                "instance_id": n.instance_id,
                "type_name": _bare_name(n.type_name),
                "params": {k: _field_value_to_python(v) for k, v in n.params.items()},
            }
            for n in mission.nodes
        ],
        "events": [
            {
                "instance_id": e.instance_id,
                "type_name": _bare_name(e.type_name),
                "params": {k: _field_value_to_python(v) for k, v in e.params.items()},
            }
            for e in mission.events
        ],
        "edges": [
            {"source": e.source, "event_id": e.event_id, "target": e.target}
            for e in mission.edges
        ],
        "start_id": mission.start_id,
        "role": mission.role,
        "imports": [
            {"alias": imp.alias, "path": imp.path, "version": imp.version}
            for imp in mission.imports
        ],
    }


class ParseDslRequest(BaseModel):
    dsl: str


@app.post("/api/parse_dsl")
async def parse_dsl(request: ParseDslRequest):
    client = _current_dslcompiler_client()
    try:
        resp = await client.parse_dsl(request.dsl)
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return parse_dsl_response_to_dict(resp)


def _bare_name(qualified: str) -> str:
    """'actions.Patrol' -> 'Patrol'. Every qualified name this service
    produces is 'qualifier.Name' with no further dots in the qualifier
    (see the dslcompiler design doc's Schema section), so the part after
    the last '.' is always the bare display name."""
    return qualified.rsplit(".", 1)[-1]


def _type_name_index(qualified_names) -> dict[str, str]:
    """Builds a bare-name -> qualified-name lookup, e.g. {'Patrol':
    'actions.Patrol'}. If two qualified names share a bare name (not the
    case for the current default import set), the later one wins --
    matches today's flat, collision-free Python-SDK-era registry closely
    enough that this isn't worth guarding further here."""
    return {_bare_name(name): name for name in qualified_names}


def _field_schema_to_dict(field: dslcompiler_pb2.FieldSchema) -> dict:
    entry: dict = {
        "name": field.name,
        "type": field.type,
        "required": field.required,
        "description": field.description,
    }
    if field.HasField("default_value"):
        entry["default"] = field.default_value
    if field.HasField("object_type"):
        entry["object_type"] = _bare_name(field.object_type)
    if field.HasField("enum_type"):
        entry["enum_type"] = _bare_name(field.enum_type)
    if field.nested_fields:
        entry["nested_fields"] = [_field_schema_to_dict(f) for f in field.nested_fields]
    return entry


def _type_schemas_to_dict(schemas: dict[str, dslcompiler_pb2.TypeSchema]) -> dict:
    return {
        _bare_name(name): {
            "description": ts.description,
            "fields": [_field_schema_to_dict(f) for f in ts.fields],
        }
        for name, ts in schemas.items()
    }


def build_schema_response(resp: dslcompiler_pb2.GetSchemaResponse) -> dict:
    """Pure function -- translates the dslcompiler service's qualified-name
    schema into the bare-name-keyed shape the frontend already consumes
    (see this plan's Global Constraints on why bare names are load-bearing
    here, not cosmetic)."""
    result = {
        "actions": _type_schemas_to_dict(resp.actions),
        "events": _type_schemas_to_dict(resp.events),
        "imports": [
            {"alias": imp.alias, "path": imp.path, "version": imp.version}
            for imp in resp.imports
        ],
        "default_role": resp.default_role,
    }
    if not result["actions"] and not result["events"]:
        raise HTTPException(
            status_code=500,
            detail="Schema registry is empty — dslcompiler service returned nothing",
        )
    return result


@app.get("/api/schema")
async def get_schema():
    client = _current_dslcompiler_client()
    try:
        resp = await client.get_schema()
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return build_schema_response(resp)


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


def _field_value_from_python(
    value, field_schema: dslcompiler_pb2.FieldSchema | None
) -> dslcompiler_pb2.FieldValue:
    """Converts one plain-JSON param value (what the current frontend still
    sends -- Phase 2 is what will let it send FieldValue's oneof kind
    explicitly) into a typed FieldValue, using field_schema (when known)
    to resolve the one real ambiguity: whether a string names an enum
    constant (ident_ref) or is a literal string value. bool is checked
    before int since Python's bool is an int subclass."""
    if isinstance(value, bool):
        return dslcompiler_pb2.FieldValue(bool_value=value)
    if (
        field_schema is not None
        and field_schema.HasField("enum_type")
        and isinstance(value, str)
    ):
        return dslcompiler_pb2.FieldValue(ident_ref=value)
    if isinstance(value, int):
        return dslcompiler_pb2.FieldValue(int_value=value)
    if isinstance(value, float):
        return dslcompiler_pb2.FieldValue(float_value=value)
    if isinstance(value, str):
        return dslcompiler_pb2.FieldValue(string_value=value)
    if isinstance(value, list):
        return dslcompiler_pb2.FieldValue(
            array_value=dslcompiler_pb2.FieldValueArray(
                elems=[_field_value_from_python(v, None) for v in value]
            )
        )
    if isinstance(value, dict):
        nested_by_name = (
            {f.name: f for f in field_schema.nested_fields} if field_schema else {}
        )
        return dslcompiler_pb2.FieldValue(
            inline_value=dslcompiler_pb2.InlineCtorValue(
                type_name=field_schema.object_type if field_schema else "",
                args={
                    k: _field_value_from_python(v, nested_by_name.get(k))
                    for k, v in value.items()
                },
            )
        )
    raise ValueError(f"Unsupported param value: {value!r}")


def _params_to_field_values(
    params: dict, fields_by_name: dict[str, dslcompiler_pb2.FieldSchema]
) -> dict[str, dslcompiler_pb2.FieldValue]:
    return {
        k: _field_value_from_python(v, fields_by_name.get(k)) for k, v in params.items()
    }


def _mission_graph_from_request(
    request: "CompileRequest", schema: dslcompiler_pb2.GetSchemaResponse
) -> dslcompiler_pb2.MissionGraph:
    """Translates the frontend's bare-name, untyped-JSON graph shape into
    the qualified-name, typed-FieldValue MissionGraph Validate/Build
    expect. An unknown bare type_name is passed through unqualified
    rather than rejected here -- Validate's own registry lookup reports a
    clear "unknown type" error naming it, so there's no need to duplicate
    that check locally (see the design doc's Graph -> AST Construction
    section on what stays a local structural check vs. what Validate
    itself is responsible for)."""
    action_index = _type_name_index(schema.actions.keys())
    event_index = _type_name_index(schema.events.keys())

    nodes = [
        dslcompiler_pb2.Node(
            instance_id=n.instance_id,
            type_name=action_index.get(n.type_name, n.type_name),
            params=_params_to_field_values(
                n.params,
                {
                    f.name: f
                    for f in schema.actions.get(
                        action_index.get(n.type_name, n.type_name),
                        dslcompiler_pb2.TypeSchema(),
                    ).fields
                },
            ),
        )
        for n in request.nodes
    ]
    events = [
        dslcompiler_pb2.EventInstance(
            instance_id=e.instance_id,
            type_name=event_index.get(e.type_name, e.type_name),
            params=_params_to_field_values(
                e.params,
                {
                    f.name: f
                    for f in schema.events.get(
                        event_index.get(e.type_name, e.type_name),
                        dslcompiler_pb2.TypeSchema(),
                    ).fields
                },
            ),
        )
        for e in request.events
    ]
    edges = [
        dslcompiler_pb2.Edge(source=e.source, event_id=e.event_id, target=e.target)
        for e in request.edges
    ]
    return dslcompiler_pb2.MissionGraph(
        nodes=nodes, events=events, edges=edges, start_id=request.start_id
    )


async def compile_mission(
    request: CompileRequest,
    client: DslCompilerClient,
    schema: dslcompiler_pb2.GetSchemaResponse,
) -> dict:
    """Pure-ish function (one gRPC call) -- safe to test with a
    FakeDslCompilerClient, no live server needed. Structural checks
    (duplicate ids, dangling edges, start_id) run locally first, exactly
    as before; only "does this type/these params actually type-check
    against the SDK" now goes over gRPC to Validate."""
    errors: list[dict] = []

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

    node_ids = {n.instance_id for n in request.nodes}
    if request.start_id not in node_ids:
        errors.append(
            {
                "node_id": request.start_id,
                "message": f"start_id '{request.start_id}' does not refer to any node",
            }
        )

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

    try:
        mission = _mission_graph_from_request(request, schema)
    except ValueError as e:
        return {"errors": [{"node_id": None, "message": str(e)}]}
    try:
        validate_resp = await client.validate(mission)
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    if not validate_resp.ok:
        return {
            "errors": [
                {
                    "node_id": e.node_id if e.HasField("node_id") else None,
                    "event_id": e.event_id if e.HasField("event_id") else None,
                    "message": e.message,
                }
                for e in validate_resp.errors
            ]
        }

    transitions: dict[str, dict[str, str]] = {}
    for edge in request.edges:
        transitions.setdefault(edge.source, {})[edge.event_id] = edge.target

    return {
        "mission": {
            "actions": {
                n.instance_id: {
                    "type_name": n.type_name,
                    "action_id": n.instance_id,
                    "attributes": n.params,
                }
                for n in request.nodes
            },
            "events": {
                e.instance_id: {
                    "type_name": e.type_name,
                    "event_id": e.instance_id,
                    "attributes": e.params,
                }
                for e in request.events
            },
            "data": {},
            "start_action_id": request.start_id,
            "transitions": transitions,
        }
    }


@app.post("/api/compile")
async def compile_mission_route(request: CompileRequest) -> dict:
    client = _current_dslcompiler_client()
    try:
        schema = await client.get_schema()
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    return await compile_mission(request, client, schema)


class BuildMissionRequest(CompileRequest):
    arch: Literal["amd64", "arm64"]


async def _build_stream_for_arch(client: DslCompilerClient, mission, arch: str):
    """Relays only the BuildChunks for arch out of the service's combined
    amd64+arm64 stream, yielding raw bytes. Raises HTTPException (rather
    than yielding an error indicator) if the FIRST chunk seen for arch
    carries errors, since that happens before any response bytes have
    been sent -- the caller must consume at least one item from this
    generator inside a try/except before handing it to StreamingResponse,
    exactly as the route below does, or the error will surface as a
    broken stream instead of a clean 422."""
    stream = client.build(mission)
    async for chunk in stream:
        if chunk.arch != arch:
            continue
        if chunk.errors:
            detail = "; ".join(e.message for e in chunk.errors)
            raise HTTPException(
                status_code=422, detail=f"Build failed for {arch}: {detail}"
            )
        yield chunk.data
        if chunk.done:
            return


@app.post("/api/build")
async def build_route(request: BuildMissionRequest):
    client = _current_dslcompiler_client()
    try:
        schema = await client.get_schema()
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    try:
        mission = _mission_graph_from_request(request, schema)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    stream = _build_stream_for_arch(client, mission, request.arch)
    try:
        first_piece = await anext(stream)
    except StopAsyncIteration:
        raise HTTPException(
            status_code=500,
            detail=f"Build stream ended without producing arch '{request.arch}'",
        ) from None
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e

    async def _relay():
        yield first_piece
        async for piece in stream:
            yield piece

    return StreamingResponse(
        _relay(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="mission-{request.arch}"'
        },
    )


# Serve Vite static files
app.mount("/", StaticFiles(directory="../prime/dist", html=True), name="react_app")
