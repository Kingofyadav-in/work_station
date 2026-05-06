from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
SHARED_DIR = ROOT_DIR / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

import local_admin_registry as _local_admin_registry  # noqa: E402


def get_local_admin_registry_state(limit: int = 500) -> dict[str, Any]:
    return _local_admin_registry.get_local_admin_users(limit=limit)


def clear_local_admin_registry() -> None:
    clear_fn = getattr(_local_admin_registry, "clear_local_admin_users", None)
    if callable(clear_fn):
        clear_fn()
        return
    # Backward-compatible fallback if the module is stale in-memory.
    registry_log = getattr(_local_admin_registry, "REGISTRY_LOG", None)
    if registry_log is not None:
        try:
            Path(registry_log).unlink()
        except FileNotFoundError:
            pass
