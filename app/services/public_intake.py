from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
SHARED_DIR = ROOT_DIR / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from public_intake import get_public_intake_summary  # noqa: E402


def get_public_inbox_state(limit: int = 100) -> dict[str, Any]:
    summary = get_public_intake_summary(limit=limit)
    return {
        "summary": summary,
        "enquiries": [item for item in summary["items"] if item.get("kind") == "enquiry"],
        "signups": [item for item in summary["items"] if item.get("kind") == "signup"],
    }
