import asyncio
import base64
import binascii
import json
import logging
import os
import time
from contextlib import asynccontextmanager

import cv2
import grpc
import numpy as np
import redis
import requests
import toml
from colorhash import ColorHash
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from steeleagle_protocol.v1.services.swarm import swarm_pb2_grpc

from app import dslcompiler_routes
from app.eagled_log_routes import router as eagled_log_router
from app.eagled_routes import router as eagled_router
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

    dslcompiler_routes.setup(cfg.get("dslcompiler"))

    yield
    # Cleanup
    for _name, conn in backend_connections.items():
        await conn.grpc_channel.close()
        conn.redis_connection.close()
    await dslcompiler_routes.teardown()


app = FastAPI(lifespan=lifespan)
app.include_router(dslcompiler_routes.router)
app.include_router(eagled_router)
app.include_router(eagled_log_router)


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


def _build_vehicle(drone_name: str, fields: dict, telem: list) -> Vehicle:
    """Build a Vehicle from its Redis hash fields and latest telemetry entry.

    Raises KeyError if a required Redis field is missing (including no
    telemetry entry at all), or ValueError -- pydantic's ValidationError is
    a ValueError subclass, so this also covers a malformed/out-of-range
    value such as an out-of-range lat/long sentinel (e.g. 500, 500) from a
    vehicle with no GPS fix. Callers should catch both and skip just this
    vehicle rather than failing the whole endpoint.
    """
    if not telem:
        raise KeyError("telemetry")
    t = telem[0][1]
    home_loc = Location(
        lat=fields["position_info.home_lat"],
        long=fields["position_info.home_long"],
        alt=fields["position_info.home_alt"],
    )
    current = Location(
        lat=t["latitude"],
        long=t["longitude"],
        alt=max(0, float(t["rel_altitude"])),
    )
    vel = Velocity(
        x_vel=t["v_body_forward"],
        y_vel=t["v_body_lateral"],
        z_vel=t["v_body_altitude"],
        angular_vel=t["v_body_angular"],
    )
    return Vehicle(
        name=drone_name,
        model=fields["model"],
        battery=t["battery"],
        sats=t["sats"],
        mag=fields["mag"],
        last_updated=round(time.time() - float(fields["last_seen"]), 2),
        home=home_loc,
        current=current,
        bearing=t["bearing"],
        velocity=vel,
    )


@app.get("/api/remote/vehicles")
async def get_vehicles() -> list[Vehicle]:
    data = []
    if backend_key is None:
        conn = backend_connections[list(backend_connections)[0]].redis_connection
    else:
        conn = backend_connections[backend_key].redis_connection
    red = conn
    for k in red.keys("vehicle:*"):
        drone_name = k.split(":")[-1]
        fields = red.hgetall(k)
        telem = red.xrevrange(f"telemetry:{drone_name}", "+", "-", 1)
        try:
            data.append(_build_vehicle(drone_name, fields, telem))
        except KeyError as e:
            logger.error(
                f"Vehicle '{drone_name}' is missing required field {e} in Redis, skipping"
            )
        except ValueError as e:
            logger.error(
                f"Vehicle '{drone_name}' has invalid telemetry data, skipping: {e}"
            )

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


# Serve Vite static files
app.mount("/", StaticFiles(directory="../prime/dist", html=True), name="react_app")
