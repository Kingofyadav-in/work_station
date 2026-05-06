from __future__ import annotations

import sys
from pathlib import Path


JARVIS_DIR = Path(__file__).resolve().parents[1]

if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))
