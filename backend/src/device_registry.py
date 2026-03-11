"""SQLite-backed device registry with hashed API keys and roles."""

import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from passlib.hash import bcrypt as _bcrypt

# ---------------------------------------------------------------------------
# Database location — stored next to this file by default; override via env.
# ---------------------------------------------------------------------------
import os

DB_PATH = os.environ.get("DEVICE_DB_PATH", str(Path(__file__).parent / "devices.db"))

_lock = threading.Lock()


@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create the devices table if it does not already exist."""
    with _lock, _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                device_id   TEXT PRIMARY KEY,
                role        TEXT NOT NULL DEFAULT 'device',
                key_hash    TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                revoked     INTEGER NOT NULL DEFAULT 0
            )
            """
        )


# ---------------------------------------------------------------------------
# Key generation and hashing helpers
# ---------------------------------------------------------------------------

_KEY_PREFIX = "m2m"
_KEY_BYTES = 32  # 256-bit entropy -> 43 base64url chars


def generate_api_key() -> str:
    """Return a new random API key (plain-text, shown once)."""
    raw = secrets.token_urlsafe(_KEY_BYTES)
    return f"{_KEY_PREFIX}_{raw}"


def hash_api_key(plain_key: str) -> str:
    """Return a bcrypt hash of the plain-text API key."""
    return _bcrypt.hash(plain_key)


def verify_api_key(plain_key: str, key_hash: str) -> bool:
    """Constant-time verification of a plain key against its stored hash."""
    try:
        return _bcrypt.verify(plain_key, key_hash)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def create_device(device_id: str, role: str = "device") -> str:
    """
    Register a new device and return the plain-text API key.
    Raises ValueError if device_id already exists.
    """
    plain_key = generate_api_key()
    key_hash = hash_api_key(plain_key)
    created_at = datetime.now(timezone.utc).isoformat()

    with _lock, _get_conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM devices WHERE device_id = ?", (device_id,)
        ).fetchone()
        if existing:
            raise ValueError(f"Device '{device_id}' already exists.")
        conn.execute(
            "INSERT INTO devices (device_id, role, key_hash, created_at, revoked) VALUES (?,?,?,?,0)",
            (device_id, role, key_hash, created_at),
        )

    return plain_key


def revoke_device(device_id: str) -> bool:
    """Mark a device as revoked. Returns True if device existed."""
    with _lock, _get_conn() as conn:
        cur = conn.execute(
            "UPDATE devices SET revoked = 1 WHERE device_id = ?", (device_id,)
        )
        return cur.rowcount > 0


def list_devices() -> list[dict]:
    """Return all devices without key hashes."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT device_id, role, created_at, revoked FROM devices ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def get_device(device_id: str) -> Optional[dict]:
    """Return a single device row (including key_hash) or None."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT device_id, role, key_hash, created_at, revoked FROM devices WHERE device_id = ?",
            (device_id,),
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Authentication helper
# ---------------------------------------------------------------------------

def authenticate(device_id: str, plain_key: str) -> Optional[dict]:
    """
    Verify device_id + plain_key against the registry.
    Returns the device dict on success, None on failure.
    Never logs the plain_key.
    """
    device = get_device(device_id)
    if device is None:
        # Use a dummy comparison to avoid timing oracle on device existence
        verify_api_key(plain_key, hash_api_key(generate_api_key()))
        return None
    if device["revoked"]:
        verify_api_key(plain_key, device["key_hash"])  # constant-time side-channel guard
        return None
    if not verify_api_key(plain_key, device["key_hash"]):
        return None
    return device
