# M2M Communication — DQN Battery Scheduling

This project implements a Deep Q-Network (DQN) combined with battery health management and sleep/awake scheduling for Wireless Sensor Networks (WSNs). The backend also exposes observability, real-time device monitoring, message schema validation, and per-device API key authentication.

## Project Structure

```
├── backend/
│   ├── src/
│   │   ├── api.py                # FastAPI server (all endpoints)
│   │   ├── device_registry.py    # SQLite device registry + API key auth
│   │   ├── schemas.py            # JSON Schema validation
│   │   ├── logging_config.py     # Structured JSON logging + request middleware
│   │   ├── dqn_agent.py          # DDQN agent implementation
│   │   ├── env_wsn.py            # WSN Gym environment
│   │   ├── compare_algorithms.py # Algorithm comparison utilities
│   │   └── utils.py              # General utilities
│   ├── templates/
│   │   ├── dashboard.html        # Real-time device dashboard (WebSocket)
│   │   └── stats.html            # Server stats page
│   ├── tests/
│   │   └── test_features.py      # Automated tests (pytest)
│   └── requirements.txt
├── frontend/                     # React simulation UI
├── schemas/
│   └── v1.json                   # M2M message JSON Schema v1
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js and npm

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

### Running the Server

```bash
cd backend

# Set the admin API key (required for admin endpoints)
export ADMIN_API_KEY=your-secret-admin-key

# Optional: override log level (default: INFO)
export LOG_LEVEL=INFO

# Optional: custom DB path (default: backend/src/devices.db)
export DEVICE_DB_PATH=/path/to/devices.db

uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm start
```

The React app is available at `http://localhost:3000` and connects to the backend at `http://localhost:8000`.

---

## Feature 1 — Observability

### Health Endpoint

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "server_time": "2024-01-15T12:00:00.000000+00:00",
  "uptime_seconds": 42.3,
  "version": "1.0.0",
  "connected_devices": 2
}
```

### Stats Page

- **HTML UI**: `GET /stats` — auto-refreshes every 10 seconds.
- **JSON API**: `GET /api/stats` — machine-readable stats.

```bash
curl http://localhost:8000/api/stats
```

### Structured Logging

All log output is JSON with fields: `timestamp`, `level`, `message`, `logger`, `request_id`, `method`, `path`, `status_code`, `latency_ms`. Secrets (`api_key`, `authorization`, `token`, etc.) are automatically redacted to `[REDACTED]`.

---

## Feature 2 — Message Schema + Validation

All inbound telemetry messages are validated against `schemas/v1.json`.

### Schema Envelope (v1)

```json
{
  "schema_version": "1.0",
  "device_id": "sensor-01",
  "timestamp": "2024-01-15T12:00:00Z",
  "type": "telemetry",
  "payload": {
    "temperature": 22.5,
    "humidity": 60
  }
}
```

| Field            | Type   | Required | Notes                              |
|------------------|--------|----------|------------------------------------|
| `schema_version` | string | ✓        | Must be `"1.0"`                    |
| `device_id`      | string | ✓        | Alphanumeric, `-`, `_`, `.` only   |
| `timestamp`      | string | ✓        | RFC 3339 / ISO-8601 date-time      |
| `type`           | string | ✓        | `telemetry` \| `command` \| `status` |
| `payload`        | object | ✓        | Arbitrary key/value pairs          |

### Send Telemetry

```bash
curl -X POST http://localhost:8000/telemetry \
  -H "Content-Type: application/json" \
  -H "X-Device-ID: sensor-01" \
  -H "X-API-Key: m2m_<your-device-key>" \
  -d '{
    "schema_version": "1.0",
    "device_id": "sensor-01",
    "timestamp": "2024-01-15T12:00:00Z",
    "type": "telemetry",
    "payload": {"temperature": 22.5}
  }'
```

Invalid messages return HTTP `422` with details:
```json
{
  "error": "Message validation failed (1 error(s)).",
  "details": ["['type']: 'bad_type' is not one of ['telemetry', 'command', 'status']"]
}
```

---

## Feature 3 — Real-time Device Dashboard

Navigate to **`http://localhost:8000/dashboard`** in your browser. The page opens a WebSocket connection to `/ws/dashboard` and shows a live table of all devices with their status, last seen time, last message type, and message count.

The dashboard auto-reconnects if the connection drops and refreshes relative-time labels every 10 seconds.

![M2M Device Dashboard](https://github.com/user-attachments/assets/ccbf6acb-6ed1-422c-bb68-51b33048b3d9)

---

## Feature 4 — Per-device API Keys + Roles

Devices and admin users are stored in a local SQLite database (`devices.db`). API keys are stored as bcrypt hashes. All key comparisons are constant-time.

### Create a Device (admin only)

```bash
curl -X POST http://localhost:8000/admin/devices \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ADMIN_API_KEY" \
  -d '{"device_id": "sensor-01", "role": "device"}'
```

Response (key shown **once only**):
```json
{
  "device_id": "sensor-01",
  "role": "device",
  "api_key": "m2m_xXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxX",
  "warning": "Store this key securely — it will not be shown again."
}
```

### List Devices

```bash
curl http://localhost:8000/admin/devices \
  -H "X-API-Key: $ADMIN_API_KEY"
```

### Revoke a Device Key

```bash
curl -X POST http://localhost:8000/admin/devices/sensor-01/revoke \
  -H "X-API-Key: $ADMIN_API_KEY"
```

### Authentication for Device Endpoints

Include both headers on every device request:

```
X-Device-ID: sensor-01
X-API-Key: m2m_<device-key>
```

### Roles

| Role     | Permissions                                                |
|----------|------------------------------------------------------------|
| `device` | POST `/telemetry`                                          |
| `admin`  | All admin endpoints (`/admin/devices`, `/stats`, `/health`) |

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```

Test coverage includes:
- Schema validation (valid, missing fields, wrong types, unknown version)
- Device registry (create, authenticate, revoke, list)
- API key hashing and constant-time verification
- `/health` endpoint response shape
- Admin CRUD endpoints
- Telemetry ingest (valid + invalid messages)
- Secret redaction in structured logs

---

## API Reference

| Method | Path                                | Auth     | Description                    |
|--------|-------------------------------------|----------|--------------------------------|
| GET    | `/health`                           | None     | Server health check            |
| GET    | `/api/stats`                        | None     | JSON stats snapshot            |
| GET    | `/stats`                            | None     | Stats HTML page                |
| GET    | `/dashboard`                        | None     | Live device dashboard UI       |
| WS     | `/ws/dashboard`                     | None     | WebSocket feed for dashboard   |
| POST   | `/telemetry`                        | Device   | Ingest validated message       |
| POST   | `/admin/devices`                    | Admin    | Register a new device          |
| GET    | `/admin/devices`                    | Admin    | List all devices               |
| POST   | `/admin/devices/{device_id}/revoke` | Admin    | Revoke a device's API key      |
| POST   | `/run_simulation`                   | None     | Run DQN battery simulation     |

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.