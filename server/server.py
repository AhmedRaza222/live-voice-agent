#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load environment variables
load_dotenv(override=True)

from bot_fast_api import run_bot
from bot_websocket_server import run_bot_websocket_server
from bot_infobip import run_infobip_bot


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles FastAPI startup and shutdown."""
    yield  # Run app


# Initialize FastAPI app with lifespan manager
app = FastAPI(lifespan=lifespan)

# Configure CORS to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if directory exists (for production serving)
# Needs to be "static" directory relative to current working directory or absolute path
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection accepted")
    try:
        await run_bot(websocket)
    except Exception as e:
        print(f"Exception in run_bot: {e}")


@app.websocket("/infobip")
async def websocket_infobip_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Infobip WebSocket connection accepted")
    try:
        await run_infobip_bot(websocket)
    except Exception as e:
        print(f"Exception in run_infobip_bot: {e}")

@app.post("/connect")
async def bot_connect(request: Request) -> Dict[Any, Any]:
    server_mode = os.getenv("WEBSOCKET_SERVER", "fast_api")
    if server_mode == "websocket_server":
        ws_url = "ws://localhost:8765"
    else:
        # Dynamic WebSocket URL generation
        scheme = "wss" if request.url.scheme == "https" else "ws"
        host = request.headers.get("host")
        ws_url = f"{scheme}://{host}/ws"
    return {"ws_url": ws_url}


async def main():
    server_mode = os.getenv("WEBSOCKET_SERVER", "fast_api")
    tasks = []
    try:
        if server_mode == "websocket_server":
            tasks.append(run_bot_websocket_server())

        config = uvicorn.Config(app, host="0.0.0.0", port=7860)
        server = uvicorn.Server(config)
        tasks.append(server.serve())

        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        print("Tasks cancelled (probably due to shutdown).")


if __name__ == "__main__":
    asyncio.run(main())
