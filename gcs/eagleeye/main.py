from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import zmq
import zmq.asyncio
import asyncio
import json
import os
import grpc

app = FastAPI()

# Initialize ZeroMQ context
zmq_context = zmq.asyncio.Context()

# gRPC client setup - persistent channel and stub
GRPC_SERVER_ADDRESS = "localhost:50051"
grpc_channel = None
grpc_stub = None

@app.on_event("startup")
async def startup_event():
    """Initialize gRPC channel on startup"""
    global grpc_channel, grpc_stub
    
    # Create persistent channel with connection pooling
    grpc_channel = grpc.aio.insecure_channel(
        GRPC_SERVER_ADDRESS
    )
    
    # Create stub - replace with your actual stub
    # grpc_stub = your_service_pb2_grpc.YourServiceStub(grpc_channel)
    
    print("gRPC channel initialized")

# API Routes
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
                    yield f": keep-alive\n\n"
        except asyncio.CancelledError:
            socket.close()
            raise
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )

@app.post("/api/command")
async def command(request: Request):
    try:
        # Get raw JSON body
        payload = await request.json()

        # TODO: Convert to protobuf and send

        return {
            "status": "success",
            "message": "gRPC call would be made here",
            "received": payload,
            # "grpc_response": MessageToDict(response)  # Convert protobuf to dict
        }

    except grpc.aio.AioRpcError as e:
        raise HTTPException(
            status_code=500,
            detail=f"gRPC call failed: {e.code()} - {e.details()}"
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )

# Serve Vite static files
app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    file_path = os.path.join("dist", full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse("dist/index.html")

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    zmq_context.term()
