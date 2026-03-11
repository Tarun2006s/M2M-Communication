"""
Automated tests for M2M Communication backend.

Run with:
    cd backend
    pytest tests/ -v
"""

import json
import os
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Ensure the src package is importable when running pytest from backend/
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Feature 2 — Schema validation tests
# ---------------------------------------------------------------------------

from src.schemas import ValidationError, validate_message  # noqa: E402


VALID_MSG = {
    "schema_version": "1.0",
    "device_id": "sensor-01",
    "timestamp": "2024-01-15T12:00:00Z",
    "type": "telemetry",
    "payload": {"temperature": 22.5},
}


class TestSchemaValidation:
    def test_valid_message_passes(self):
        result = validate_message(VALID_MSG.copy())
        assert result["device_id"] == "sensor-01"

    def test_missing_required_field_fails(self):
        msg = {k: v for k, v in VALID_MSG.items() if k != "device_id"}
        with pytest.raises(ValidationError) as exc_info:
            validate_message(msg)
        assert "device_id" in str(exc_info.value) or exc_info.value.details

    def test_missing_schema_version_fails(self):
        msg = {k: v for k, v in VALID_MSG.items() if k != "schema_version"}
        with pytest.raises(ValidationError) as exc_info:
            validate_message(msg)
        assert "schema_version" in str(exc_info.value)

    def test_wrong_type_field_fails(self):
        msg = {**VALID_MSG, "type": "invalid_type"}
        with pytest.raises(ValidationError):
            validate_message(msg)

    def test_wrong_device_id_type_fails(self):
        msg = {**VALID_MSG, "device_id": 12345}
        with pytest.raises(ValidationError):
            validate_message(msg)

    def test_wrong_payload_type_fails(self):
        msg = {**VALID_MSG, "payload": "not-an-object"}
        with pytest.raises(ValidationError):
            validate_message(msg)

    def test_non_dict_input_fails(self):
        with pytest.raises(ValidationError):
            validate_message([1, 2, 3])

    def test_unknown_schema_version_fails(self):
        msg = {**VALID_MSG, "schema_version": "99.0"}
        with pytest.raises(ValidationError) as exc_info:
            validate_message(msg)
        assert "Unknown schema version" in str(exc_info.value)

    def test_command_type_is_valid(self):
        msg = {**VALID_MSG, "type": "command"}
        result = validate_message(msg)
        assert result["type"] == "command"

    def test_status_type_is_valid(self):
        msg = {**VALID_MSG, "type": "status"}
        result = validate_message(msg)
        assert result["type"] == "status"

    def test_empty_payload_is_valid(self):
        msg = {**VALID_MSG, "payload": {}}
        result = validate_message(msg)
        assert result["payload"] == {}

    def test_invalid_device_id_chars_fail(self):
        msg = {**VALID_MSG, "device_id": "bad device!@#"}
        with pytest.raises(ValidationError):
            validate_message(msg)


# ---------------------------------------------------------------------------
# Feature 4 — Device registry tests
# ---------------------------------------------------------------------------

from src.device_registry import (  # noqa: E402
    authenticate,
    create_device,
    hash_api_key,
    init_db,
    list_devices,
    revoke_device,
    verify_api_key,
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    """Each test gets its own clean SQLite database."""
    db_file = str(tmp_path / "test_devices.db")
    monkeypatch.setenv("DEVICE_DB_PATH", db_file)
    # Patch the module-level DB_PATH used by device_registry
    import src.device_registry as dr
    monkeypatch.setattr(dr, "DB_PATH", db_file)
    init_db()
    yield


class TestDeviceRegistry:
    def test_create_device_returns_key(self):
        key = create_device("dev-001", "device")
        assert key.startswith("m2m_")

    def test_create_duplicate_device_raises(self):
        create_device("dev-dup")
        with pytest.raises(ValueError, match="already exists"):
            create_device("dev-dup")

    def test_key_hash_not_equal_to_plain(self):
        key = "m2m_supersecret"
        hashed = hash_api_key(key)
        assert hashed != key

    def test_verify_correct_key_succeeds(self):
        key = create_device("dev-verify")
        import src.device_registry as dr
        device = dr.get_device("dev-verify")
        assert verify_api_key(key, device["key_hash"])

    def test_verify_wrong_key_fails(self):
        create_device("dev-wrong")
        import src.device_registry as dr
        device = dr.get_device("dev-wrong")
        assert not verify_api_key("m2m_wrong_key", device["key_hash"])

    def test_authenticate_valid_credentials(self):
        key = create_device("dev-auth")
        result = authenticate("dev-auth", key)
        assert result is not None
        assert result["device_id"] == "dev-auth"

    def test_authenticate_invalid_key(self):
        create_device("dev-badkey")
        result = authenticate("dev-badkey", "m2m_invalid")
        assert result is None

    def test_authenticate_unknown_device(self):
        result = authenticate("nonexistent", "m2m_somekey")
        assert result is None

    def test_authenticate_revoked_device(self):
        key = create_device("dev-revoke")
        revoke_device("dev-revoke")
        result = authenticate("dev-revoke", key)
        assert result is None

    def test_revoke_nonexistent_returns_false(self):
        assert revoke_device("ghost-device") is False

    def test_list_devices_does_not_include_key_hash(self):
        create_device("dev-list-01")
        create_device("dev-list-02")
        devices = list_devices()
        assert len(devices) == 2
        for d in devices:
            assert "key_hash" not in d

    def test_admin_role(self):
        key = create_device("admin-device", role="admin")
        result = authenticate("admin-device", key)
        assert result["role"] == "admin"


# ---------------------------------------------------------------------------
# Feature 1 — Observability HTTP tests  (using FastAPI TestClient)
# ---------------------------------------------------------------------------

import pytest  # noqa: F811 (already imported above, just a reminder)

try:
    from fastapi.testclient import TestClient
    _TESTCLIENT_AVAILABLE = True
except ImportError:
    _TESTCLIENT_AVAILABLE = False

_skip_http = pytest.mark.skipif(
    not _TESTCLIENT_AVAILABLE, reason="httpx not installed"
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient with a fresh DB and admin key configured."""
    db_file = str(tmp_path / "api_test.db")
    monkeypatch.setenv("DEVICE_DB_PATH", db_file)
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")

    import src.device_registry as dr
    monkeypatch.setattr(dr, "DB_PATH", db_file)
    init_db()

    # Re-import api after env is patched so ADMIN_KEY is picked up
    import importlib
    import src.api as api_module
    monkeypatch.setattr(api_module, "ADMIN_KEY", "test-admin-key")

    return TestClient(api_module.app)


@_skip_http
class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_contains_required_fields(self, client):
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert "server_time" in data
        assert "uptime_seconds" in data
        assert "version" in data
        assert "connected_devices" in data

    def test_health_uptime_is_positive(self, client):
        data = client.get("/health").json()
        assert data["uptime_seconds"] >= 0


@_skip_http
class TestStatsEndpoint:
    def test_api_stats_returns_200(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200

    def test_stats_page_returns_html(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


@_skip_http
class TestAdminEndpoints:
    def test_create_device_returns_key(self, client):
        resp = client.post(
            "/admin/devices",
            json={"device_id": "test-device", "role": "device"},
            headers={"X-API-Key": "test-admin-key"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["device_id"] == "test-device"
        assert data["api_key"].startswith("m2m_")

    def test_create_device_without_admin_key_fails(self, client):
        # When ADMIN_API_KEY is configured but no key is provided, expect 403
        resp = client.post(
            "/admin/devices",
            json={"device_id": "test-device-2", "role": "device"},
        )
        assert resp.status_code == 403

    def test_create_device_with_wrong_admin_key_fails(self, client):
        resp = client.post(
            "/admin/devices",
            json={"device_id": "test-device-3", "role": "device"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 403

    def test_list_devices(self, client):
        client.post(
            "/admin/devices",
            json={"device_id": "list-dev", "role": "device"},
            headers={"X-API-Key": "test-admin-key"},
        )
        resp = client.get("/admin/devices", headers={"X-API-Key": "test-admin-key"})
        assert resp.status_code == 200
        ids = [d["device_id"] for d in resp.json()["devices"]]
        assert "list-dev" in ids

    def test_revoke_device(self, client):
        client.post(
            "/admin/devices",
            json={"device_id": "revoke-me"},
            headers={"X-API-Key": "test-admin-key"},
        )
        resp = client.post(
            "/admin/devices/revoke-me/revoke",
            headers={"X-API-Key": "test-admin-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "revoked"


@_skip_http
class TestTelemetryEndpoint:
    def test_valid_telemetry_accepted(self, client):
        # Create a device first
        resp = client.post(
            "/admin/devices",
            json={"device_id": "telem-dev"},
            headers={"X-API-Key": "test-admin-key"},
        )
        api_key = resp.json()["api_key"]

        msg = {
            "schema_version": "1.0",
            "device_id": "telem-dev",
            "timestamp": "2024-01-15T12:00:00Z",
            "type": "telemetry",
            "payload": {"temperature": 25.0},
        }
        resp = client.post(
            "/telemetry",
            json=msg,
            headers={"X-Device-ID": "telem-dev", "X-API-Key": api_key},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_invalid_message_rejected(self, client):
        resp = client.post(
            "/admin/devices",
            json={"device_id": "bad-telem-dev"},
            headers={"X-API-Key": "test-admin-key"},
        )
        api_key = resp.json()["api_key"]

        msg = {"schema_version": "1.0", "device_id": "bad-telem-dev"}  # missing fields
        resp = client.post(
            "/telemetry",
            json=msg,
            headers={"X-Device-ID": "bad-telem-dev", "X-API-Key": api_key},
        )
        assert resp.status_code == 422

    def test_unauthenticated_telemetry_rejected(self, client):
        msg = VALID_MSG.copy()
        resp = client.post("/telemetry", json=msg)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Feature 1C — Structured logging / secret redaction
# ---------------------------------------------------------------------------

from src.logging_config import JsonFormatter, _redact  # noqa: E402


class TestLogging:
    def test_redact_api_key(self):
        data = {"api_key": "m2m_supersecret", "message": "hello"}
        result = _redact(data)
        assert result["api_key"] == "[REDACTED]"
        assert result["message"] == "hello"

    def test_redact_authorization_header(self):
        data = {"authorization": "Bearer tok123"}
        result = _redact(data)
        assert result["authorization"] == "[REDACTED]"

    def test_redact_is_case_insensitive(self):
        data = {"X-API-Key": "secret"}
        result = _redact(data)
        assert result["X-API-Key"] == "[REDACTED]"

    def test_non_secret_fields_not_redacted(self):
        data = {"device_id": "dev-01", "level": "INFO"}
        result = _redact(data)
        assert result == data

    def test_nested_redaction(self):
        data = {"headers": {"authorization": "Bearer xyz"}}
        result = _redact(data)
        assert result["headers"]["authorization"] == "[REDACTED]"
