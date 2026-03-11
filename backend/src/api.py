"""
M2M Communication Backend API
==============================
FastAPI server exposing:
  - Existing simulation endpoint  (/run_simulation)
  - Feature 1: Observability      (/health, /api/stats, /stats)
  - Feature 2: Schema validation  (/telemetry)
  - Feature 3: WS dashboard       (/ws/dashboard, /dashboard)
  - Feature 4: Device auth/admin  (X-API-Key, /admin/devices)
"""

import asyncio
import hmac as _hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .device_registry import (
    authenticate,
    create_device,
    init_db,
    list_devices,
    revoke_device,
)
from .dqn_agent import DDQNAgent
from .env_wsn import WSNEnv
from .logging_config import RequestLoggingMiddleware, configure_logging
from .schemas import ValidationError, validate_message

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("m2m.api")

_START_TIME = time.time()
_APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")

# ---------------------------------------------------------------------------
# In-memory stats counters (module-level, thread-safe enough for single worker)
# ---------------------------------------------------------------------------

_stats: dict[str, Any] = {
    "total_requests": 0,
    "requests_per_endpoint": {},
    "messages_received": 0,
    "messages_validated": 0,
    "messages_rejected": 0,
    "ws_connections_current": 0,
    "ws_connections_total": 0,
}

# ---------------------------------------------------------------------------
# Device telemetry state (device_id -> dict with last_seen etc.)
# ---------------------------------------------------------------------------
_device_state: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# WebSocket connection manager for /ws/dashboard clients
# ---------------------------------------------------------------------------

class DashboardManager:
    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)
        _stats["ws_connections_current"] += 1
        _stats["ws_connections_total"] += 1

    def disconnect(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)
        _stats["ws_connections_current"] = max(0, _stats["ws_connections_current"] - 1)

    async def broadcast(self, message: dict):
        data = json.dumps(message, default=str)
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


_dashboard = DashboardManager()

# ---------------------------------------------------------------------------
# Lifespan: initialise DB on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app_: FastAPI):
    init_db()
    logger.info("Database initialised", extra={"event": "startup"})
    yield
    logger.info("Server shutting down", extra={"event": "shutdown"})


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(title="M2M Communication API", version=_APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# ---------------------------------------------------------------------------
# Middleware: count requests per endpoint
# ---------------------------------------------------------------------------

@app.middleware("http")
async def _count_requests(request: Request, call_next):
    _stats["total_requests"] += 1
    endpoint = request.url.path
    _stats["requests_per_endpoint"][endpoint] = (
        _stats["requests_per_endpoint"].get(endpoint, 0) + 1
    )
    return await call_next(request)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")


def _require_admin(request: Request):
    """Raise 403 if the request does not carry the admin API key."""
    if not ADMIN_KEY:
        # Admin key not configured — admin endpoints are disabled.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key not configured (set ADMIN_API_KEY env var).",
        )
    provided = request.headers.get("X-API-Key", "")
    # constant-time comparison
    if not _hmac.compare_digest(provided, ADMIN_KEY):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")


def _require_device(request: Request) -> dict:
    """
    Authenticate a device request via X-Device-ID + X-API-Key headers.
    Returns the device dict on success; raises HTTP 401 on failure.
    """
    device_id = request.headers.get("X-Device-ID", "")
    api_key = request.headers.get("X-API-Key", "")
    if not device_id or not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Device-ID and X-API-Key headers are required.",
        )
    device = authenticate(device_id, api_key)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credentials.",
        )
    return device


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SimulationRequest(BaseModel):
    seed: int
    N: int
    episodes: int
    max_steps: int


class SimulationResult(BaseModel):
    rewards: list
    average_lifetime: float
    total_energy: float
    battery_history: list = []
    soh_history: list = []


class CreateDeviceRequest(BaseModel):
    device_id: str
    role: str = "device"


# ---------------------------------------------------------------------------
# Template loader helper
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _render_html(filename: str) -> HTMLResponse:
    path = _TEMPLATE_DIR / filename
    return HTMLResponse(content=path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Feature 1 — Observability
# ---------------------------------------------------------------------------

@app.get("/health", tags=["observability"])
async def health():
    """Returns server health in JSON (HTTP 200)."""
    return {
        "status": "ok",
        "server_time": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - _START_TIME, 2),
        "version": _APP_VERSION,
        "connected_devices": len(_device_state),
    }


@app.get("/api/stats", tags=["observability"])
async def api_stats():
    """JSON stats snapshot used by the /stats page."""
    return {
        **_stats,
        "uptime_seconds": round(time.time() - _START_TIME, 2),
        "connected_devices": {
            k: {
                "last_seen": v.get("last_seen"),
                "last_message_type": v.get("last_message_type"),
                "message_count": v.get("message_count", 0),
            }
            for k, v in _device_state.items()
        },
    }


@app.get("/stats", response_class=HTMLResponse, tags=["observability"])
async def stats_page():
    """Server-rendered stats HTML page."""
    return _render_html("stats.html")


# ---------------------------------------------------------------------------
# Feature 2 — Schema validation + telemetry ingest
# ---------------------------------------------------------------------------

@app.post("/telemetry", tags=["telemetry"])
async def ingest_telemetry(request: Request, device: dict = Depends(_require_device)):
    """
    Ingest a device telemetry message.
    Requires X-Device-ID + X-API-Key headers.
    Body must conform to schemas/v1.json.
    """
    _stats["messages_received"] += 1

    try:
        body = await request.json()
    except Exception:
        _stats["messages_rejected"] += 1
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")

    try:
        validated = validate_message(body)
    except ValidationError as exc:
        _stats["messages_rejected"] += 1
        logger.warning(
            "Message rejected",
            extra={"device_id": device["device_id"], "reason": str(exc), "details": exc.details},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": str(exc), "details": exc.details},
        )

    _stats["messages_validated"] += 1

    device_id = validated["device_id"]
    now = datetime.now(timezone.utc).isoformat()
    prev = _device_state.get(device_id, {})
    _device_state[device_id] = {
        "device_id": device_id,
        "last_seen": now,
        "last_message_type": validated.get("type"),
        "message_count": prev.get("message_count", 0) + 1,
        "role": device.get("role", "device"),
    }

    # Push real-time update to dashboard WebSocket clients
    await _dashboard.broadcast(
        {
            "type": "telemetry_update",
            "device": _device_state[device_id],
        }
    )

    logger.info(
        "Telemetry ingested",
        extra={"device_id": device_id, "message_type": validated.get("type")},
    )
    return {"status": "ok", "device_id": device_id}


# ---------------------------------------------------------------------------
# Feature 3 — Real-time device dashboard
# ---------------------------------------------------------------------------

@app.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
async def dashboard_page():
    """Live device dashboard UI (WebSocket-powered)."""
    return _render_html("dashboard.html")


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """WebSocket endpoint for the live device dashboard."""
    await _dashboard.connect(websocket)
    logger.info("Dashboard client connected", extra={"event": "ws_connect"})

    # Send current full state immediately so the UI doesn't start blank
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "full_state",
                    "devices": list(_device_state.values()),
                },
                default=str,
            )
        )
        # Keep connection alive — real updates come from broadcast()
        while True:
            await asyncio.sleep(15)
            # Heartbeat ping to keep the connection open
            await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _dashboard.disconnect(websocket)
        logger.info("Dashboard client disconnected", extra={"event": "ws_disconnect"})


# ---------------------------------------------------------------------------
# Feature 4 — Admin / device management
# ---------------------------------------------------------------------------

@app.post(
    "/admin/devices",
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def admin_create_device(
    body: CreateDeviceRequest,
    request: Request,
):
    """Create a new device and return its API key (shown once)."""
    _require_admin(request)
    try:
        plain_key = create_device(body.device_id, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    logger.info("Device created", extra={"device_id": body.device_id, "role": body.role})
    # The plain key is returned once; it is NOT logged.
    return {
        "device_id": body.device_id,
        "role": body.role,
        "api_key": plain_key,
        "warning": "Store this key securely — it will not be shown again.",
    }


@app.get("/admin/devices", tags=["admin"])
async def admin_list_devices(request: Request):
    """List all registered devices (no key hashes)."""
    _require_admin(request)
    return {"devices": list_devices()}


@app.post("/admin/devices/{device_id}/revoke", tags=["admin"])
async def admin_revoke_device(device_id: str, request: Request):
    """Revoke a device's API key."""
    _require_admin(request)
    ok = revoke_device(device_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    logger.info("Device revoked", extra={"device_id": device_id})
    return {"status": "revoked", "device_id": device_id}


# ---------------------------------------------------------------------------
# Existing simulation endpoint (unchanged)
# ---------------------------------------------------------------------------

@app.post("/run_simulation", response_model=SimulationResult, tags=["simulation"])
async def run_simulation(request: SimulationRequest):
    env = WSNEnv(N=request.N, max_steps=request.max_steps, seed=request.seed)
    state_dim = env.observation_space.shape[0]
    action_dim = 2
    agent = DDQNAgent(state_dim, action_dim, node_count=request.N)

    rewards_history = []
    steps_alive_history = []
    total_energy = 0.0
    battery_history = []
    soh_history = []

    for ep in range(request.episodes):
        state = env.reset()
        ep_reward = 0.0
        done = False
        steps_alive = 0
        ep_energy = 0.0

        ep_soc = []
        ep_soh = []

        while not done:
            action = agent.select_action(state)
            next_state, reward, done, info = env.step(action)

            ep_soc.append(float(env.soc.mean() / env.E_max))
            ep_soh.append(float(env.soh.mean()))

            agent.store(state, action, reward, next_state, done)
            agent.train_step()

            state = next_state
            ep_reward += reward
            steps_alive += 1
            if "total_energy" in info:
                ep_energy += info["total_energy"]

        rewards_history.append(ep_reward)
        steps_alive_history.append(steps_alive)
        total_energy += ep_energy

        if ep == request.episodes - 1:
            battery_history = ep_soc.copy()
            soh_history = ep_soh.copy()

    average_lifetime = float(np.mean(steps_alive_history)) if steps_alive_history else 0.0

    return SimulationResult(
        rewards=rewards_history,
        average_lifetime=average_lifetime,
        total_energy=total_energy,
        battery_history=battery_history,
        soh_history=soh_history,
    )


@app.get("/", tags=["root"])
async def root():
    return {"message": "Welcome to the M2M Communication API!"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )