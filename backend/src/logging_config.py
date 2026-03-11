"""Structured JSON logging configuration for the M2M backend."""

import json
import logging
import time
import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# JSON log formatter
# ---------------------------------------------------------------------------

_REDACTED = "[REDACTED]"
_SECRET_FIELDS = frozenset({"api_key", "x-api-key", "authorization", "token", "secret", "password"})


def _redact(record_dict: dict) -> dict:
    """Recursively redact known secret field names."""
    result = {}
    for k, v in record_dict.items():
        if k.lower() in _SECRET_FIELDS:
            result[k] = _REDACTED
        elif isinstance(v, dict):
            result[k] = _redact(v)
        else:
            result[k] = v
    return result


class JsonFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_dict = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        # Attach any extra fields that were passed via extra={}
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
            ):
                log_dict[key] = value
        log_dict = _redact(log_dict)
        return json.dumps(log_dict, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Replace the root handler with a JSON formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


# ---------------------------------------------------------------------------
# Request-ID / latency middleware
# ---------------------------------------------------------------------------

logger = logging.getLogger("m2m.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach a request_id to each request and log method / path / latency."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        response: Response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        # Build log extras; redact Authorization header
        headers = dict(request.headers)
        for secret_header in ("authorization", "x-api-key"):
            if secret_header in headers:
                headers[secret_header] = _REDACTED

        logger.info(
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response
