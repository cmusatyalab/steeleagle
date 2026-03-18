import asyncio
import base64
import io
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
import zmq
import zmq.asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, NonNegativeInt
from pydantic_extra_types.coordinate import Latitude, Longitude
from rich.logging import RichHandler
from steeleagle_sdk.protocol.messages.telemetry_pb2 import DriverTelemetry, Frame
from steeleagle_sdk.protocol.services.control_service_pb2 import (
    HoldRequest,
    JoystickRequest,
    LandRequest,
    PoseMode,
    ReturnToHomeRequest,
    SetGimbalPoseTargetRequest,
    TakeOffRequest,
)
from steeleagle_sdk.protocol.services.control_service_pb2_grpc import ControlStub
from steeleagle_sdk.protocol.services.mission_service_pb2 import (
    StartRequest,
    StopRequest,
    UploadRequest,
)
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionStub
from steeleagle_sdk.protocol.services.remote_service_pb2 import (
    CommandRequest,
)
from steeleagle_sdk.protocol.services.remote_service_pb2_grpc import RemoteStub

IDENTITY_MD = (("identity", "server"),)
FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("rich")
uvicorn_access = logging.getLogger("uvicorn.access")
uvicorn_access.disabled = True

backend_key = os.getenv("BACKEND")


class Start(BaseModel):
    vehicles: list[str]


class Upload(BaseModel):
    kml: str
    dsl: str
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


class VehicleConnection(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    grpc_channel: grpc.aio.Channel
    telemetry_endpoint: zmq.Socket
    imagery_endpoint: zmq.Socket
    control_stub: ControlStub
    mission_stub: MissionStub


class BackendConnection(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    grpc_channel: grpc.aio.Channel
    remote_stub: RemoteStub
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

# Initialize ZeroMQ context
zmq_context = zmq.asyncio.Context()
vehicle_data: dict[str, Vehicle] = {}
vehicle_connections: dict[str, VehicleConnection] = {}
backend_connections: dict[str, BackendConnection] = {}
connection_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    for v in cfg["vehicle"]:
        vehicle = cfg["vehicle"][v]
        logger.info(f"Creating connections to vehicle {v}...")
        channel = grpc.aio.insecure_channel(vehicle["address"])
        control_stub = ControlStub(channel)
        mission_stub = MissionStub(channel)
        logger.info(
            f" **{v}** Opened control and missions stubs at GRPC endpoint: {vehicle['address']}"
        )
        tel_sock = zmq_context.socket(zmq.SUB)
        tel_sock.setsockopt_string(zmq.SUBSCRIBE, "")
        tel_sock.connect(vehicle["tel_endpoint"])
        logger.info(
            f" **{v}** Subscribed to ZMQ telemetry at: {vehicle['tel_endpoint']}"
        )
        image_sock = zmq_context.socket(zmq.SUB)
        image_sock.setsockopt_string(zmq.SUBSCRIBE, "")
        image_sock.setsockopt(zmq.RCVHWM, 2)
        image_sock.connect(vehicle["img_endpoint"])
        logger.info(f" **{v}** Subscribed to ZMQ imagery at: {vehicle['img_endpoint']}")
        vc = VehicleConnection(
            grpc_channel=channel,
            control_stub=control_stub,
            mission_stub=mission_stub,
            imagery_endpoint=image_sock,
            telemetry_endpoint=tel_sock,
        )
        vehicle_connections[v] = vc
        logger.info(f"Added VehicleConnection for {v}!")

    for name, conn in vehicle_connections.items():
        asyncio.create_task(
            _telemetry_subscriber(
                conn.telemetry_endpoint,
                name=name,
            )
        )

        asyncio.create_task(
            _imagery_broadcaster(
                conn.imagery_endpoint,
                name=name,
            )
        )

    for b in cfg["backend"]:
        backend = cfg["backend"][b]
        swarm_controller_channel = grpc.aio.insecure_channel(
            backend["swarm-controller"]
        )
        remote_stub = RemoteStub(swarm_controller_channel)
        logger.info(
            f" **{b}** Opened remote stubs at GRPC endpoint: {backend['swarm-controller']}"
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
            grpc_channel=channel,
            remote_stub=remote_stub,
            redis_connection=red,
            webserver=webserver,
            show_detections=True,
        )
        backend_connections[b] = bc

    yield
    # Cleanup
    for _name, conn in backend_connections.items():
        await conn.grpc_channel.close()
        conn.redis_connection.close()
    for _name, conn in vehicle_connections.items():
        conn.telemetry_endpoint.close()
        conn.imagery_endpoint.close()
        await conn.grpc_channel.close()
    zmq_context.term()


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg["cors"]["origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _send_stream(call, vehicle: str, command: str):
    try:
        # For server-streaming RPCs
        async for response in call:
            logger.debug(f"[{vehicle}] Response for {command}: {response.status}")
    except grpc.aio.AioRpcError as e:
        logger.error(f"[{vehicle}] Error during {command}: {e}")


async def _send_unary(call, vehicle: str, command: str):
    try:
        # assuming unary RPC that just acks
        await call
    except grpc.aio.AioRpcError as e:
        logger.error(f"[{vehicle}] Error during {command}: {e}")


async def _telemetry_subscriber(sock, name: str):
    while True:
        if sock:
            try:
                # Receive message from ZeroMQ (non-blocking)
                message = await sock.recv_multipart(flags=zmq.NOBLOCK)
                tel = DriverTelemetry()
                tel.ParseFromString(message[1])
                current = Location(
                    lat=tel.position_info.global_position.latitude,
                    long=tel.position_info.global_position.longitude,
                    alt=max(0, float(tel.position_info.global_position.altitude)),
                )

                vel = Velocity(
                    x_vel=tel.position_info.velocity_body.x_vel,
                    y_vel=tel.position_info.velocity_body.y_vel,
                    z_vel=tel.position_info.velocity_body.z_vel,
                    angular_vel=tel.position_info.velocity_body.angular_vel,
                )

                v = Vehicle(
                    name=tel.vehicle_info.name,
                    model=tel.vehicle_info.model,
                    battery=tel.vehicle_info.battery_info.percentage,
                    sats=tel.alert_info.gps_warning,
                    mag=tel.alert_info.magnetometer_warning,
                    last_updated=0,
                    current=current,
                    bearing=tel.position_info.global_position.heading,
                    velocity=vel,
                )
                vehicle_data[name] = v
            except zmq.Again:
                await asyncio.sleep(0.01)


async def _imagery_broadcaster(sock, name: str):
    """
    Background task that continuously reads imagery from ZMQ and broadcasts to all WebSocket clients
    """
    logger.debug(f"Starting imagery broadcaster for '{name}'")
    while True:
        if sock:
            try:
                # Receive message from ZeroMQ (non-blocking)
                message = await sock.recv_multipart(flags=zmq.DONTWAIT)
                frame = Frame()
                frame.ParseFromString(message[1])
                encoded_img = Image.frombuffer(
                    mode="RGB", size=(frame.h_res, frame.v_res), data=frame.data
                )
                # resized = encoded_img.resize((320, 180))
                img_bytes = io.BytesIO()
                encoded_img.save(img_bytes, format="JPEG")

                # Encode to base64 and broadcast to all connected clients
                base64_image = base64.b64encode(img_bytes.getvalue()).decode("ascii")
                await connection_manager.broadcast(name, base64_image)

            except zmq.Again:
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error in imagery broadcaster for {name}: {e}")
                await asyncio.sleep(0.1)


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
                nparr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if conn.show_detections:
                    maybe_add_bboxes(vehicle, img)
                add_watermark(img)
                _, img_bytes = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
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

    key = f"latest-detection:{vehicle_id}"
    raw = red.lrange(key, 0, -1)
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

    CLASS_COLORS = {
        "person": (0, 255, 120),
    }
    DEFAULT_COLOR = (200, 200, 200)

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
        color = CLASS_COLORS.get(cls, DEFAULT_COLOR)

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
                sats=fields["sats"],
                mag=fields["mag"],
                last_updated=round(time.time() - float(fields["last_seen"]), 2),
                home=home_loc,
                current=current,
                bearing=bearing,
                velocity=vel,
            )
        )

    return data


@app.get("/api/local/vehicles")
async def get_local_vehicles(name: str = None) -> list[Vehicle]:
    return vehicle_data.values()


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


@app.websocket("/ws/imagery/{vehicle}")
async def websocket_endpoint(websocket: WebSocket, vehicle: str):
    if vehicle == "":
        await websocket.close(code=1008, reason="Vehicle name required")
        return

    if vehicle not in vehicle_connections:
        await websocket.close(code=1008, reason=f"Vehicle '{vehicle}' not found")
        return

    await connection_manager.connect(websocket, vehicle)

    try:
        # Keep the connection alive and handle any incoming messages
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from /ws/imagery/{vehicle}")
    except Exception as e:
        logger.error(f"WebSocket error for vehicle '{vehicle}': {e}")
    finally:
        await connection_manager.disconnect(websocket, vehicle)


@app.post("/api/gimbal")
async def set_gimbal_pose(req: GimbalPose, sandbox_mode: bool = True) -> JSONResponse:
    for v in req.vehicles:
        if sandbox_mode:
            conn = vehicle_connections[v]
        else:
            if backend_key is None:
                conn = backend_connections[list(backend_connections)[0]]
            else:
                conn = backend_connections[backend_key]
        _ = conn.grpc_channel.get_state(
            try_to_connect=True
        )  # attempt to reconnect to grpc endpoint
        try:
            g = SetGimbalPoseTargetRequest()
            g.gimbal_id = 0
            g.pose_mode = PoseMode.OFFSET
            g.pose.pitch = req.pitch
            g.pose.yaw = req.yaw
            g.pose.roll = req.roll
            if sandbox_mode:
                call = conn.control_stub.SetGimbalPoseTarget(g, metadata=IDENTITY_MD)
                asyncio.create_task(
                    _send_unary(call, vehicle=v, command="control.SetGimbalPoseTarget")
                )
            else:
                cmd = CommandRequest()
                cmd.method_name = "Control.SetGimbalPoseTarget"
                cmd.vehicle_id = v
                cmd.request.Pack(g)
                call = backend_connections[
                    list(backend_connections)[0]
                ].remote_stub.Command(cmd)
                asyncio.create_task(
                    _send_stream(call, vehicle=v, command="SetGimbalPoseTarget")
                )

        except grpc.aio.AioRpcError as e:
            raise HTTPException(
                status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
            ) from e
        except json.JSONDecodeError as e:
            logger.error(e)
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from e
        except Exception as e:
            logger.error(e)
            raise HTTPException(status_code=500, detail=f"Error: {e.message}") from e
    return JSONResponse(status_code=200, content="Mission start sent!")


@app.post("/api/start")
async def start(req: Start, sandbox_mode: bool = True) -> JSONResponse:
    for v in req.vehicles:
        if sandbox_mode:
            conn = vehicle_connections[v]
        else:
            if backend_key is None:
                conn = backend_connections[list(backend_connections)[0]]
            else:
                conn = backend_connections[backend_key]
        _ = conn.grpc_channel.get_state(
            try_to_connect=True
        )  # attempt to reconnect to grpc endpoint
        try:
            start = StartRequest()
            if sandbox_mode:
                call = conn.mission_stub.Start(start, metadata=IDENTITY_MD)
                asyncio.create_task(
                    _send_unary(call, vehicle=v, command="mission.start")
                )
            else:
                cmd = CommandRequest()
                cmd.method_name = "Mission.Start"
                cmd.vehicle_id = v
                cmd.request.Pack(start)
                call = backend_connections[
                    list(backend_connections)[0]
                ].remote_stub.Command(cmd)
                asyncio.create_task(
                    _send_stream(call, vehicle=v, command="remote mission start")
                )

        except grpc.aio.AioRpcError as e:
            raise HTTPException(
                status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
            ) from e
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from e
        except Exception as e:
            logger.error(e)
            raise HTTPException(status_code=500, detail=f"Error: {e.message}") from e
    return JSONResponse(status_code=200, content="Mission start sent!")


@app.post("/api/upload")
async def upload(req: Upload, sandbox_mode: bool = True) -> JSONResponse:
    for v in req.vehicles:
        if sandbox_mode:
            conn = vehicle_connections[v]
        else:
            if backend_key is None:
                conn = backend_connections[list(backend_connections)[0]]
            else:
                conn = backend_connections[backend_key]
        _ = conn.grpc_channel.get_state(
            try_to_connect=True
        )  # attempt to reconnect to grpc endpoint
        try:
            up = UploadRequest()
            up.mission.map = base64.b64decode(req.kml)
            up.mission.content = base64.b64decode(req.dsl)
            if sandbox_mode:
                call = conn.mission_stub.Upload(up, metadata=IDENTITY_MD)
                asyncio.create_task(
                    _send_unary(call, vehicle=v, command="mission.upload")
                )
            else:
                cmd = CommandRequest()
                cmd.method_name = "Mission.Upload"
                cmd.vehicle_id = v
                cmd.request.Pack(up)
                call = backend_connections[
                    list(backend_connections)[0]
                ].remote_stub.Command(cmd)
                asyncio.create_task(
                    _send_stream(call, vehicle=v, command="remote mission upload")
                )

        except grpc.aio.AioRpcError as e:
            raise HTTPException(
                status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
            ) from e
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from e
        except Exception as e:
            logger.error(e)
            raise HTTPException(status_code=500, detail=f"Error: {e.message}") from e
    return JSONResponse(status_code=200, content="Mission upload complete!")


@app.post("/api/joystick")
async def joystick(req: Joystick, sandbox_mode: bool = True) -> JSONResponse:
    for v in req.vehicles:
        if sandbox_mode:
            conn = vehicle_connections[v]
        else:
            if backend_key is None:
                conn = backend_connections[list(backend_connections)[0]]
            else:
                conn = backend_connections[backend_key]
        _ = conn.grpc_channel.get_state(
            try_to_connect=True
        )  # attempt to reconnect to grpc endpoint
        try:
            joy = JoystickRequest()
            joy.velocity.x_vel = req.xvel
            joy.velocity.y_vel = req.yvel
            joy.velocity.z_vel = req.zvel
            joy.velocity.angular_vel = req.angularvel
            joy.duration.seconds = req.duration
            if sandbox_mode:
                call = conn.control_stub.Joystick(joy, metadata=IDENTITY_MD)
                asyncio.create_task(_send_unary(call, vehicle=v, command="joystick"))
            else:
                cmd = CommandRequest()
                cmd.method_name = "Control.Joystick"
                cmd.vehicle_id = v
                cmd.request.Pack(joy)
                call = backend_connections[
                    list(backend_connections)[0]
                ].remote_stub.Command(cmd)
                asyncio.create_task(
                    _send_stream(call, vehicle=v, command="remote joystick")
                )

        except grpc.aio.AioRpcError as e:
            raise HTTPException(
                status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
            ) from e
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from e
        except Exception as e:
            logger.error(e)
            raise HTTPException(status_code=500, detail=f"Error: {e.message}") from e
    return JSONResponse(status_code=200, content="Joystick movement complete!")


@app.post("/api/command")
async def command(req: Command, sandbox_mode: bool = True) -> JSONResponse:
    response = None
    for v in req.vehicles:
        logger.info(f"Sending command to {v}...")
        if sandbox_mode:
            conn = vehicle_connections[v]
        else:
            if backend_key is None:
                conn = backend_connections[list(backend_connections)[0]]
            else:
                conn = backend_connections[backend_key]
        _ = conn.grpc_channel.get_state(
            try_to_connect=True
        )  # attempt to reconnect to grpc endpoint
        try:
            cmd = CommandRequest()
            cmd.vehicle_id = v
            if req.takeoff is not None:
                takeoff = TakeOffRequest()
                takeoff.take_off_altitude = req.takeoff
                if sandbox_mode:
                    call = conn.control_stub.TakeOff(takeoff, metadata=IDENTITY_MD)
                    asyncio.create_task(
                        _send_stream(call, vehicle=v, command="takeoff")
                    )
                else:
                    cmd.method_name = "Control.TakeOff"
                    cmd.request.Pack(takeoff)
                    call = conn.remote_stub.Command(cmd)
                    asyncio.create_task(
                        _send_stream(call, vehicle=v, command="remote takeoff")
                    )
                response = JSONResponse(status_code=200, content="Takeoff complete!")
            elif req.land:
                land = LandRequest()
                if sandbox_mode:
                    call = conn.control_stub.Land(land, metadata=IDENTITY_MD)
                    asyncio.create_task(_send_stream(call, vehicle=v, command="land"))
                else:
                    cmd.method_name = "Control.Land"
                    cmd.request.Pack(land)
                    call = conn.remote_stub.Command(cmd)
                    asyncio.create_task(
                        _send_stream(call, vehicle=v, command="remote land")
                    )
                response = JSONResponse(status_code=200, content="Landing complete!")
            elif req.rth:
                rth = ReturnToHomeRequest()
                if sandbox_mode:
                    call = conn.control_stub.ReturnToHome(rth, metadata=IDENTITY_MD)
                    asyncio.create_task(_send_stream(call, vehicle=v, command="rth"))
                else:
                    cmd.method_name = "Control.ReturnToHome"
                    cmd.request.Pack(rth)
                    call = conn.remote_stub.Command(cmd)
                    asyncio.create_task(
                        _send_stream(call, vehicle=v, command="remote rth")
                    )
                response = JSONResponse(
                    status_code=200, content="Return to Home command sent."
                )
            elif req.hold:
                hold = HoldRequest()
                stop = StopRequest()
                if sandbox_mode:
                    call = conn.control_stub.Hold(hold, metadata=IDENTITY_MD)
                    asyncio.create_task(_send_stream(call, vehicle=v, command="hold"))
                    call = conn.mission_stub.Stop(stop, metadata=IDENTITY_MD)
                    asyncio.create_task(
                        _send_unary(call, vehicle=v, command="mission.stop")
                    )
                else:
                    cmd.method_name = "Control.Hold"
                    cmd.request.Pack(hold)
                    call = conn.remote_stub.Command(cmd)
                    asyncio.create_task(
                        _send_stream(call, vehicle=v, command="remote hold")
                    )
                    cmd.method_name = "Mission.Stop"
                    cmd.request.Pack(stop)
                    call = conn.remote_stub.Command(cmd)
                    asyncio.create_task(
                        _send_stream(call, vehicle=v, command="remote stop")
                    )

                response = JSONResponse(
                    status_code=200,
                    content="Mission canceled and vehicle instructed to hold.",
                )
        except grpc.aio.AioRpcError as e:
            raise HTTPException(
                status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
            ) from e
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from e
        except Exception as e:
            logger.error(e)
            raise HTTPException(status_code=500, detail=f"Error: {e.message}") from e
    return response


# Serve Vite static files
app.mount("/", StaticFiles(directory="../prime/dist", html=True), name="react_app")
