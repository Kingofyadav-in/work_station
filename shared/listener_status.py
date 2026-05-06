#!/usr/bin/env python3
from __future__ import annotations

import os
import time
from pathlib import Path


def find_listener_pid() -> int | None:
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmdline = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "ignore")
            if "app.py" not in cmdline or "streamlit" in cmdline:
                continue
            cwd = os.readlink(proc / "cwd")
            if cwd.endswith("/Kingofyadav"):
                return int(proc.name)
        except Exception:
            continue
    return None


def pid_file_is_recent(pid_path: Path, max_age_seconds: int = 300) -> bool:
    try:
        return (time.time() - pid_path.stat().st_mtime) < max_age_seconds
    except Exception:
        return False


def resolve_listener_pid(pid_path: Path) -> int | None:
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return pid
    except PermissionError:
        return None
    except (FileNotFoundError, ValueError, ProcessLookupError):
        pid = find_listener_pid()
        if pid is not None:
            try:
                pid_path.parent.mkdir(parents=True, exist_ok=True)
                pid_path.write_text(str(pid), encoding="utf-8")
            except Exception:
                pass
            return pid
        return None
