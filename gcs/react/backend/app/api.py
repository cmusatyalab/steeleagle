from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import zmq
import zmq.asyncio
import asyncio
import json
import grpc
import redis
import toml
import time
from pydantic import BaseModel, Field, NonNegativeInt, NonNegativeFloat
from pydantic_extra_types.coordinate import Latitude, Longitude
from steeleagle_sdk.protocol.services.control_service_pb2 import (
    TakeOffRequest,
)

from steeleagle_sdk.protocol.services.control_service_pb2_grpc import ControlStub
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionStub

app = FastAPI()


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
    home: Location
    current: Location
    bearing: NonNegativeInt


# Initialize ZeroMQ context
zmq_context = zmq.asyncio.Context()

# gRPC client setup - persistent channel and stub
grpc_channel = None
control_tub = mission_stub = None
red = None

origins = [
    "http://localhost:5173",
    "localhost:5173",
    "128.2.212.60:5173",
    "http://128.2.212.60:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Read TOML config and initialize connections on startup"""
    global grpc_channel, grpc_stub, red, control_stub, mission_stub

    with open("config.toml", "r") as file:
        cfg = toml.load(file)
    # Create persistent channel with connection pooling
    grpc_channel = grpc.aio.insecure_channel(cfg["grpc"]["endpoint"])

    # Create stub - replace with your actual stub
    control_stub = ControlStub(grpc_channel)
    mission_stub = MissionStub(grpc_channel)

    print("gRPC channel initialized")
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


@app.get("/api/stream")
async def stream_zmq():
    """Stream ZeroMQ messages to the client via SSE"""

    async def event_generator():
        # Create ZeroMQ subscriber socket
        socket = zmq_context.socket(zmq.SUB)
        socket.connect("tcp://localhost:5555")  # Adjust to your ZMQ address
        socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages

        try:
            while True:
                # Receive message from ZeroMQ (non-blocking)
                try:
                    message = await socket.recv_string(flags=zmq.NOBLOCK)
                    # Format as SSE
                    yield f"data: {json.dumps({'message': message})}\n\n"
                except zmq.Again:
                    # No message available, wait a bit
                    await asyncio.sleep(0.1)
                    # Send keep-alive comment
                    yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            socket.close()
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        },
    )


@app.get("/api/command")
async def command():
    try:
        takeoff = TakeOffRequest()
        takeoff.take_off_altitude = 10.0
        call = control_stub.TakeOff
        async for response in call(takeoff, metadata=(("identity", "server"),)):
            print(f"Response for takeoff: {response.status}")
        print(response)

        return {
            response,
        }

    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500, detail=f"gRPC call failed: {e.code()} - {e.details()}"
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


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
    zmq_context.term()
