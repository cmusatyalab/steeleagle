import asyncio
import base64
import io
import json
import logging
import time

import grpc
import redis
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
from steeleagle_sdk.protocol.messages.telemetry_pb2 import DriverTelemetry, Frame
from steeleagle_sdk.protocol.services.control_service_pb2 import (
    HoldRequest,
    JoystickRequest,
    LandRequest,
    ReturnToHomeRequest,
    TakeOffRequest,
)
from steeleagle_sdk.protocol.services.control_service_pb2_grpc import ControlStub
from steeleagle_sdk.protocol.services.mission_service_pb2 import (
    StartRequest,
    StopRequest,
    UploadRequest,
)
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionStub

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
app = FastAPI()

IDENTITY_MD = (("identity", "server"),)


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


class CommandRequest(BaseModel):
    takeoff: bool | None = None
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


class VehicleConnection(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    grpc_channel: grpc.aio.Channel
    telemetry_endpoint: zmq.Socket
    imagery_endpoint: zmq.Socket
    control_stub: ControlStub
    mission_stub: MissionStub


# Initialize ZeroMQ context
zmq_context = zmq.asyncio.Context()
vehicle_data: dict[str, Vehicle] = {}
vehicle_connections: dict[str, VehicleConnection] = {}
red = None

with open("config.toml") as file:
    cfg = toml.load(file)

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

                v = Vehicle(
                    name=tel.vehicle_info.name,
                    model=tel.vehicle_info.model,
                    battery=tel.alert_info.battery_warning,
                    sats=tel.alert_info.gps_warning,
                    mag=tel.alert_info.magnetometer_warning,
                    last_updated=0,
                    current=current,
                    bearing=tel.position_info.global_position.heading,
                )
                vehicle_data[name] = v
            except zmq.Again:
                await asyncio.sleep(0.01)


@app.on_event("startup")
async def startup_event():
    """Read TOML config and initialize connections on startup"""
    global grpc_channel, grpc_stub, red, zmq_context

    with open("config.toml") as file:
        cfg = toml.load(file)

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
        image_sock.setsockopt(zmq.CONFLATE, 1)
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

    red = redis.Redis(
        host=cfg["redis"]["host"],
        port=cfg["redis"]["port"],
        username=cfg["redis"]["username"],
        password=cfg["redis"]["password"],
        decode_responses=True,
    )


# API Routes
@app.get("/api/vehicles")
async def get_vehicles(name: str = None) -> list[Vehicle]:
    data = []
    current = Location(lat=42, long=-79, alt=0)
    bearing = 0
    if name is not None:
        fields = red.hgetall(f"vehicle:{name}")
        data[name] = fields
    else:
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
            data.append(
                Vehicle(
                    name=fields["name"],
                    model=fields["model"],
                    battery=fields["battery"],
                    sats=fields["sats"],
                    mag=fields["mag"],
                    last_updated=round(time.time() - float(fields["last_seen"]), 2),
                    home=home_loc,
                    current=current,
                    bearing=bearing,
                )
            )

    return data


@app.get("/api/local/vehicles")
async def get_local_vehicles(name: str = None) -> list[Vehicle]:
    return vehicle_data.values()


@app.websocket("/ws/imagery/{vehicle}")
async def websocket_endpoint(websocket: WebSocket, vehicle: str):
    await websocket.accept()
    logger.info(f"Selected vehicle {vehicle} for imagery")
    while vehicle != "":
        try:
            if vehicle_connections[vehicle].imagery_endpoint:
                # Receive message from ZeroMQ (non-blocking)
                message = await vehicle_connections[vehicle].imagery_endpoint.recv(
                    flags=zmq.DONTWAIT
                )
                frame = Frame()
                frame.ParseFromString(message)
                encoded_img = Image.frombuffer(
                    mode="RGB", size=(frame.h_res, frame.v_res), data=frame.data
                )
                resized = encoded_img.resize((320, 180))
                # resized.save("/tmp/driver_imagery.jpg")
                img_bytes = io.BytesIO()
                # resized.save(img_bytes, format='JPEG')
                encoded_img.save(img_bytes, format="JPEG")
                await websocket.send_text(
                    {base64.b64encode(img_bytes.getvalue()).decode("ascii")}
                )
            else:
                await asyncio.sleep(0.5)
        except zmq.Again:
            await asyncio.sleep(0.01)
        except WebSocketDisconnect:
            await websocket.close(code=1000, reason=None)


@app.post("/api/start")
async def start(req: Start) -> JSONResponse:
    for v in req.vehicles:
        conn = vehicle_connections[v]
        _ = conn.grpc_channel.get_state(
            try_to_connect=True
        )  # attempt to reconnect to grpc endpoint

        try:
            start = StartRequest()
            call = conn.mission_stub.Start(start, metadata=IDENTITY_MD)
            asyncio.create_task(_send_unary(call, vehicle=v, command="mission.start"))

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
async def upload(req: Upload) -> JSONResponse:
    for v in req.vehicles:
        conn = vehicle_connections[v]
        _ = conn.grpc_channel.get_state(
            try_to_connect=True
        )  # attempt to reconnect to grpc endpoint

        try:
            up = UploadRequest()
            up.mission.map = base64.b64decode(req.kml)
            up.mission.content = base64.b64decode(req.dsl)
            call = conn.mission_stub.Upload(up, metadata=IDENTITY_MD)
            asyncio.create_task(_send_unary(call, vehicle=v, command="mission.upload"))

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
async def joystick(req: Joystick, name: str = None) -> JSONResponse:
    for v in req.vehicles:
        conn = vehicle_connections[v]
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
            call = conn.control_stub.Joystick(joy, metadata=IDENTITY_MD)
            asyncio.create_task(_send_unary(call, vehicle=v, command="joystick"))

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
async def command(req: CommandRequest, name: str = None) -> JSONResponse:
    response = None
    headers = {}
    for v in req.vehicles:
        logger.info(f"Sending command to {v}...")
        conn = vehicle_connections[v]
        _ = conn.grpc_channel.get_state(
            try_to_connect=True
        )  # attempt to reconnect to grpc endpoint
        try:
            if req.takeoff:
                takeoff = TakeOffRequest()
                takeoff.take_off_altitude = 10.0
                call = conn.control_stub.TakeOff(takeoff, metadata=IDENTITY_MD)
                asyncio.create_task(_send_stream(call, vehicle=v, command="takeoff"))
                response = JSONResponse(status_code=200, content="Takeoff complete!")
            elif req.land:
                land = LandRequest()
                call = conn.control_stub.Land(land, metadata=IDENTITY_MD)
                asyncio.create_task(_send_stream(call, vehicle=v, command="land"))
                response = JSONResponse(status_code=200, content="Landing complete!")
            elif req.rth:
                rth = ReturnToHomeRequest()
                call = conn.control_stub.ReturnToHome(rth, metadata=IDENTITY_MD)
                asyncio.create_task(_send_stream(call, vehicle=v, command="rth"))
                response = JSONResponse(
                    status_code=200, content="Return to Home command sent."
                )
            elif req.hold:
                hold = HoldRequest()
                call = conn.control_stub.Hold(hold, metadata=IDENTITY_MD)
                asyncio.create_task(_send_stream(call, vehicle=v, command="hold"))
                stop = StopRequest()
                call = conn.mission_stub.Stop(stop, metadata=IDENTITY_MD)
                asyncio.create_task(
                    _send_unary(call, vehicle=v, command="mission.stop")
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


# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    for _name, conn in vehicle_connections.items():
        conn.telemetry_endpoint.close()
        conn.imagery_endpoint.close()
        conn.grpc_channel.close()
    zmq_context.term()
