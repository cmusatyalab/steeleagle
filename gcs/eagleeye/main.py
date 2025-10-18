from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Your API routes
@app.get("/api/hello")
async def hello():
    return {"message": "Hello from FastAPI"}

# Mount static files (CSS, JS, images, etc.)
app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

# Serve index.html for all other routes (SPA fallback)
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Check if it's a file request
    file_path = os.path.join("dist", full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    
    # Otherwise serve index.html (for client-side routing)
    return FileResponse("dist/index.html")
