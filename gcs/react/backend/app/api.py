import asyncio
import base64
import io
import json
import logging
import os
import random
import time

import grpc
import redis
import toml
import zmq
import zmq.asyncio
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from google.protobuf.message import DecodeError
from PIL import Image
from pydantic import BaseModel, Field, NonNegativeFloat, NonNegativeInt
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


class Upload(BaseModel):
    kml: str
    dsl: str


class Joystick(BaseModel):
    xvel: float = Field(default=0.0)
    yvel: float = Field(default=0.0)
    zvel: float = Field(default=0.0)
    angularvel: float = Field(default=0.0)
    duration: int = Field(default=1)


class CommandRequest(BaseModel):
    takeoff: bool | None = None
    land: bool | None = None
    rth: bool | None = None
    hold: bool | None = None
    stop_mission: bool | None = None
    arm: bool | None = None


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


# Initialize ZeroMQ context
zmq_context = zmq.asyncio.Context()

# gRPC client setup - persistent channel and stub
grpc_channel = None
control_stub = mission_stub = None
red = None
tel_sock = image_sock = None

with open("config.toml") as file:
    cfg = toml.load(file)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg["cors"]["origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Read TOML config and initialize connections on startup"""
    global \
        grpc_channel, \
        grpc_stub, \
        red, \
        control_stub, \
        mission_stub, \
        tel_sock, \
        image_sock, \
        zmq_context

    with open("config.toml") as file:
        cfg = toml.load(file)
    # Create persistent channel with connection pooling
    grpc_channel = grpc.aio.insecure_channel(cfg["grpc"]["endpoint"])

    # Create stub - replace with your actual stub
    control_stub = ControlStub(grpc_channel)
    mission_stub = MissionStub(grpc_channel)

    logger.info("gRPC channel initialized")
    red = redis.Redis(
        host=cfg["redis"]["host"],
        port=cfg["redis"]["port"],
        username=cfg["redis"]["username"],
        password=cfg["redis"]["password"],
        decode_responses=True,
    )

    # Create ZeroMQ subscriber sockets
    tel_sock = zmq_context.socket(zmq.SUB)
    tel_sock.connect(cfg["zmq"]["driver_telemetry"])
    tel_sock.setsockopt_string(zmq.SUBSCRIBE, "")
    image_sock = zmq_context.socket(zmq.SUB)
    image_sock.connect(cfg["zmq"]["imagery"])
    image_sock.setsockopt_string(zmq.SUBSCRIBE, "")
    if tel_sock:
        logger.info(f"Subscribed to telemetry at {cfg['zmq']['driver_telemetry']} ")
    if image_sock:
        logger.info(f"Subscribed to imagery at {cfg['zmq']['imagery']} ")


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


@app.get("/api/location")
async def get_location(name: str = None) -> Location:
    loc = None
    if name is not None:
        if red.exists(f"telemetry:{name}"):
            results = red.xrevrange(f"telemetry:{name}", "+", "-", 1)
            for item in results:
                loc = item[1]
            return Location(
                lat=loc["latitude"], long=loc["longitude"], alt=loc["rel_altitude"]
            )
        else:
            raise HTTPException(
                status_code=404, detail=f"telemetry:{name} key not found."
            )
    else:
        raise HTTPException(status_code=404, detail="Vehicle name not specified.")


@app.get("/api/local/vehicle")
async def stream_zmq():
    """Stream ZeroMQ messages to the client via SSE"""

    async def event_generator():
        try:
            while True:
                try:
                    # Receive message from ZeroMQ (non-blocking)
                    message = await tel_sock.recv_multipart(flags=zmq.NOBLOCK)
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

                    # Format as SSE
                    event_str = "event: driver_telemetry"
                    data_str = f"data: {json.dumps(v.dict())}"
                    yield f"{event_str}\n{data_str}\n\n"
                except zmq.Again:
                    # No message available, wait a bit
                    await asyncio.sleep(0.1)
                    # Send keep-alive comment
                    yield ": keep-alive\n\n"
                except DecodeError as de:
                    logger.error(f"{de} {message}!")
                    yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            logging.error("Client canceled SSE.")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        },
    )


def generate_random_jpg(filename, width=256, height=256):
    """
    Generates an image with random pixels and saves it as a JPG file.

    Args:
        filename (str): The name of the output JPG file.
        width (int): The width of the image in pixels.
        height (int): The height of the image in pixels.
    """
    # Calculate the total number of bytes needed for RGB (3 bytes per pixel)
    # The bytes must be a linear sequence of R, G, B values
    total_bytes = width * height * 3

    # Generate a list of random integer values (0-255) for the pixels
    rand_pixels = [random.randint(0, 255) for _ in range(total_bytes)]

    # Convert the list to a bytes object
    rand_pixels_as_bytes = bytes(rand_pixels)

    # Create an image from the raw bytes using Image.frombytes
    # Mode 'RGB' means 3 bytes per pixel, (width, height) specifies dimensions
    try:
        random_image = Image.frombytes("RGB", (width, height), rand_pixels_as_bytes)

        # Save the image as a JPEG file
        random_image.save(filename, format="JPEG")
        print(f"Successfully generated random image: {filename}")

    except ValueError as e:
        print(f"Error creating image: {e}")
        print("Ensure width and height match the number of bytes provided.")


@app.get("/driver_imagery")
async def get_image():
    file_path = "/tmp/driver_imagery.jpg"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/jpeg")
    return {"error": "Image not found"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        try:
            if image_sock:
                # Receive message from ZeroMQ (non-blocking)
                message = await image_sock.recv_multipart(flags=zmq.NOBLOCK)
                frame = Frame()
                frame.ParseFromString(message[1])
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
                await websocket.send_text("keep-alive")
        except zmq.Again:
            await asyncio.sleep(0.1)


@app.post("/api/start")
async def start(name: str = None) -> JSONResponse:
    _ = grpc_channel.get_state(
        try_to_connect=True
    )  # attempt to reconnect to grpc endpoint

    try:
        start = StartRequest()
        call = mission_stub.Start
        await call(start, metadata=(("identity", "server"),))

        return JSONResponse(status_code=200, content="Mission start sent!")
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from e
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"Error: {e.message}") from e


@app.post("/api/upload")
async def upload(req: Upload, name: str = None) -> JSONResponse:
    _ = grpc_channel.get_state(
        try_to_connect=True
    )  # attempt to reconnect to grpc endpoint

    try:
        up = UploadRequest()
        up.mission.map = base64.b64decode(req.kml)
        up.mission.content = base64.b64decode(req.dsl)
        call = mission_stub.Upload
        await call(up, metadata=(("identity", "server"),))

        return JSONResponse(status_code=200, content="Mission upload complete!")
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from e
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"Error: {e.message}") from e


@app.post("/api/joystick")
async def joystick(req: Joystick, name: str = None) -> JSONResponse:
    _ = grpc_channel.get_state(
        try_to_connect=True
    )  # attempt to reconnect to grpc endpoint

    try:
        joy = JoystickRequest()
        joy.velocity.x_vel = req.xvel
        joy.velocity.y_vel = req.yvel
        joy.velocity.z_vel = req.zvel
        joy.velocity.angular_vel = req.angularvel
        joy.duration.seconds = req.duration
        call = control_stub.Joystick
        await call(joy, metadata=(("identity", "server"),))

        return JSONResponse(status_code=200, content="Joystick movement complete!")
    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        ) from e
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from e
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"Error: {e.message}") from e


@app.post("/api/command")
async def command(req: CommandRequest, name: str = None) -> JSONResponse:
    _ = grpc_channel.get_state(
        try_to_connect=True
    )  # attempt to reconnect to grpc endpoint
    try:
        if req.takeoff:
            takeoff = TakeOffRequest()
            takeoff.take_off_altitude = 10.0
            call = control_stub.TakeOff
            async for response in call(takeoff, metadata=(("identity", "server"),)):
                logger.info(f"Response for takeoff: {response.status}")

            return JSONResponse(status_code=200, content="Takeoff complete!")
        elif req.land:
            land = LandRequest()
            call = control_stub.Land
            async for response in call(land, metadata=(("identity", "server"),)):
                logger.info(f"Response for land: {response.status}")

            return JSONResponse(status_code=200, content="Landing complete!")
        elif req.rth:
            rth = ReturnToHomeRequest()
            call = control_stub.ReturnToHome
            async for response in call(rth, metadata=(("identity", "server"),)):
                logger.info(f"Response for rth: {response.status}")

            return JSONResponse(status_code=200, content="Return to Home command sent.")
        elif req.hold:
            hold = HoldRequest()
            call = control_stub.Hold
            async for response in call(hold, metadata=(("identity", "server"),)):
                logger.info(f"Response for hold: {response.status}")
            stop = StopRequest()
            call = mission_stub.Stop
            await call(stop, metadata=(("identity", "server"),))

            return JSONResponse(
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


# Serve Vite static files
# app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

"""
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    file_path = os.path.join("dist", full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse("dist/index.html")
"""


# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    if tel_sock:
        tel_sock.close()
    if image_sock:
        image_sock.close()
    zmq_context.term()
