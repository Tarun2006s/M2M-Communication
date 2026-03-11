# M2M Communication — Backend

FastAPI backend for the DQN Battery Scheduling / M2M Communication project. Provides the simulation API, observability endpoints, real-time WebSocket dashboard, schema-validated telemetry ingest, and per-device API key management.

## Quick Start

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Set the admin API key

The admin key protects device-management endpoints (`/admin/devices`). Pick any secret string:

```bash
# Linux / macOS
export ADMIN_API_KEY=your-secret-admin-key

# Windows (PowerShell)
$env:ADMIN_API_KEY = "your-secret-admin-key"
```

### 3. Start the server

```bash
# From the backend/ directory:
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

Or using Python directly:

```bash
python -m uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

The API is now available at **http://localhost:8000**.

### 4. Open the UI pages

| Page | URL |
|------|-----|
| API docs (Swagger) | http://localhost:8000/docs |
| Live device dashboard | http://localhost:8000/dashboard |
| Server stats | http://localhost:8000/stats |
| Health check | http://localhost:8000/health |

---

## API Endpoints

### Observability
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server health + uptime |
| GET | `/api/stats` | JSON stats snapshot |
| GET | `/stats` | Stats HTML page |

### Telemetry
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/telemetry` | X-Device-ID + X-API-Key | Ingest a validated message |

### Dashboard
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard` | Live device dashboard UI |
| WS | `/ws/dashboard` | WebSocket feed |

### Admin (requires `X-API-Key: $ADMIN_API_KEY`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/devices` | Create device + get API key |
| GET | `/admin/devices` | List devices |
| POST | `/admin/devices/{id}/revoke` | Revoke a device key |

### Simulation
| Method | Path | Description |
|--------|------|-------------|
| POST | `/run_simulation` | Run DQN battery simulation |

---

## Example: Create a device and send telemetry

```bash
# 1. Create a device (admin only)
curl -X POST http://localhost:8000/admin/devices \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ADMIN_API_KEY" \
  -d '{"device_id": "sensor-01", "role": "device"}'
# → returns {"api_key": "m2m_...", ...}

# 2. Send telemetry with the returned key
curl -X POST http://localhost:8000/telemetry \
  -H "Content-Type: application/json" \
  -H "X-Device-ID: sensor-01" \
  -H "X-API-Key: m2m_..." \
  -d '{
    "schema_version": "1.0",
    "device_id": "sensor-01",
    "timestamp": "2024-01-15T12:00:00Z",
    "type": "telemetry",
    "payload": {"temperature": 22.5}
  }'
```

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_API_KEY` | *(unset — admin disabled)* | Secret key for admin endpoints |
| `LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`) |
| `DEVICE_DB_PATH` | `src/devices.db` | Path to SQLite device database |
| `APP_VERSION` | `1.0.0` | Version string returned by `/health` |

---

## License

MIT License. See the LICENSE file for details.
