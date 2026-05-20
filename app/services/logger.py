"""Centralised logging configuration for the Jarvis dashboard.

Import and use:
    from services.logger import get_logger
    logger = get_logger(__name__)
    logger.warning("state read failed: %s", e)

Writes to:
  - stderr (always)
  - logs/dashboard.log (rotating, 5 MB × 3 files)
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_LOG_PATH = _ROOT / "logs" / "dashboard.log"
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_FORMATTER = logging.Formatter(
    fmt="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    root = logging.getLogger("jarvis")
    root.setLevel(logging.DEBUG)

    # Rotating file handler — 5 MB × 3 backups
    fh = logging.handlers.RotatingFileHandler(
        _LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_FORMATTER)

    # Stream handler — WARNING+ to stderr so Streamlit shows critical issues
    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(_FORMATTER)

    root.addHandler(fh)
    root.addHandler(sh)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    # Prefix all loggers under "jarvis" namespace so they share the handler
    if not name.startswith("jarvis."):
        name = f"jarvis.{name.split('.')[-1]}"
    return logging.getLogger(name)
