#!/usr/bin/env python3
"""Shared identity primitives: stable IDs, fingerprints, host info, connectivity."""
from __future__ import annotations

import hashlib
import os
import socket
import uuid
from datetime import datetime, timezone


def generate_id(prefix: str) -> str:
    """Generate a stable prefixed UUID. Call once and persist — never regenerate."""
    return f"{prefix}-{uuid.uuid4()}"


def make_fingerprint(*parts: str) -> str:
    """SHA-256 of colon-joined parts. Deterministic and tamper-evident."""
    raw = ":".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def get_system_username() -> str:
    """Derive username from the host OS environment."""
    for key in ("USER", "USERNAME", "LOGNAME"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    try:
        import pwd
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        pass
    return get_hostname().split(".")[0]


def check_network(host: str = "8.8.8.8", port: int = 53, timeout: float = 1.0) -> bool:
    """Return True if host has outbound network connectivity."""
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
        return True
    except OSError:
        return False
