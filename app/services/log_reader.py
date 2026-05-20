from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from services.logger import get_logger

logger = get_logger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
BUS_LOG_PATH = ROOT_DIR / "logs" / "bus.log"
EVENTS_DIR = ROOT_DIR / "shared" / "events"
PROCESSED_DIR = ROOT_DIR / "shared" / "bus" / "processed"


def _tail_lines(path: Path, lines: int = 20) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.warning("_tail_lines failed %s: %s", path.name, e)
        return []
    return content[-lines:]


def _parse_bus_line(line: str) -> str:
    try:
        obj = json.loads(line)
        return f"[{obj.get('ts', '')}] {obj.get('msg', line)}"
    except Exception:
        return line


def read_bus_log(lines: int = 20) -> list[str]:
    raw = _tail_lines(BUS_LOG_PATH, lines=lines)
    return [_parse_bus_line(line) for line in raw]


def read_bus_log_filtered(lines: int = 20, keyword: str = "") -> list[str]:
    raw = _tail_lines(BUS_LOG_PATH, lines=max(lines * 10, 500))
    entries = [_parse_bus_line(line) for line in raw]
    if not keyword:
        return entries[-lines:]
    keyword_upper = keyword.upper()
    filtered = [line for line in entries if keyword_upper in line.upper()]
    return filtered[-lines:]


def read_event_lines(lines: int = 20) -> list[str]:
    try:
        files = sorted(EVENTS_DIR.glob("*.jsonl"))
    except Exception as e:
        logger.warning("read_event_lines glob failed: %s", e)
        return []
    if not files:
        return []
    collected: list[str] = []
    for path in reversed(files):
        chunk = _tail_lines(path, lines=lines - len(collected))
        collected = chunk + collected
        if len(collected) >= lines:
            break
    return collected[-lines:]


def read_event_objects(lines: int = 20) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for line in read_event_lines(lines=lines):
        try:
            objects.append(json.loads(line))
        except Exception:
            continue
    return objects


def get_last_event() -> dict[str, Any] | None:
    objects = read_event_objects(lines=1)
    return objects[-1] if objects else None


def get_last_bus_log_line() -> str:
    lines = read_bus_log(lines=1)
    return lines[-1] if lines else ""


def get_last_bus_log_time() -> str:
    line = get_last_bus_log_line()
    if not line:
        return "none"
    match = re.match(r"^\[([^\]]+)\]", line)
    return match.group(1) if match else "unknown"


def read_processed_ids(limit: int = 10) -> list[str]:
    try:
        files = sorted(PROCESSED_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception as e:
        logger.warning("read_processed_ids failed: %s", e)
        return []
    return [path.name for path in files[:limit]]
