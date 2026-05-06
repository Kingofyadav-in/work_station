#!/usr/bin/env python3
from __future__ import annotations

import getpass
import hashlib
import json
import os
import platform
import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from system_info import get_system_info

ROOT_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT_DIR / "logs" / "device_registry.json"

SAFE_ENV_KEYS = (
    "API_HOST",
    "API_PORT",
    "ALLOWED_ORIGIN",
    "JARVIS_PUBLIC_CHAT",
    "JARVIS_PUBLIC_CHAT_RPM",
    "JARVIS_PUBLIC_SITE_ROOT",
    "OLLAMA_HOST",
    "OPENAI_MODEL",
)
SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASS", "CREDENTIAL")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _machine_id_hash() -> str:
    raw = _read_text(Path("/etc/machine-id")) or _read_text(Path("/var/lib/dbus/machine-id"))
    return _hash(raw)[:24] if raw else "unavailable"


def _network_interfaces() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    sys_net = Path("/sys/class/net")
    if not sys_net.exists():
        return out
    for iface in sorted(sys_net.iterdir()):
        if not iface.is_dir():
            continue
        mac = _read_text(iface / "address")
        out.append({
            "name": iface.name,
            "state": _read_text(iface / "operstate") or "unknown",
            "mac_hash": _hash(mac)[:16] if mac else "unavailable",
        })
    return out


def _stable_network_hash(interfaces: list[dict[str, str]]) -> str:
    values = sorted(
        item.get("mac_hash", "")
        for item in interfaces
        if item.get("name") != "lo" and item.get("mac_hash") not in {"", "unavailable"}
    )
    return _hash("|".join(values))[:24] if values else "unavailable"


def _disk_summary() -> dict[str, str]:
    usage = shutil.disk_usage(ROOT_DIR)
    return {
        "path": str(ROOT_DIR),
        "total": str(usage.total),
        "used": str(usage.used),
        "free": str(usage.free),
    }


def _python_packages() -> dict[str, str]:
    packages: dict[str, str] = {}
    for name in ("openai", "anthropic", "streamlit", "watchdog", "rapidfuzz"):
        try:
            module = __import__(name)
            packages[name] = str(getattr(module, "__version__", "installed"))
        except Exception:
            packages[name] = "not installed"
    return packages


def _environment_summary() -> dict[str, Any]:
    safe_values = {key: os.getenv(key, "") for key in SAFE_ENV_KEYS if os.getenv(key) is not None}
    configured_secret_names = sorted(
        key for key in os.environ
        if any(marker in key.upper() for marker in SECRET_MARKERS)
    )
    return {
        "safe_values": safe_values,
        "configured_secret_names": configured_secret_names,
        "secret_values_stored": False,
    }


def collect_device_inventory() -> dict[str, Any]:
    system = get_system_info()
    uname = platform.uname()
    interfaces = _network_interfaces()
    network_hash = _stable_network_hash(interfaces)
    inventory = {
        "identity": {
            "hostname": socket.gethostname(),
            "user": getpass.getuser(),
            "machine_id_hash": _machine_id_hash(),
            "network_hash": network_hash,
        },
        "hardware": {
            "machine": uname.machine,
            "processor": uname.processor or platform.processor() or "unavailable",
            "cpu_cores": system.get("cpu_cores", "unavailable"),
            "total_memory": system.get("total_memory", "unavailable"),
            "disk": _disk_summary(),
        },
        "software": {
            "operating_system": system.get("operating_system", "unavailable"),
            "os_version": system.get("os_version", "unavailable"),
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "packages": _python_packages(),
        },
        "network": {
            "hostname": system.get("hostname", socket.gethostname()),
            "local_ip": system.get("local_ip", "unavailable"),
            "connectivity": system.get("connectivity", "unknown"),
            "interfaces": interfaces,
        },
        "environment": _environment_summary(),
    }
    fingerprint_basis = {
        "hostname": inventory["identity"]["hostname"],
        "machine_id_hash": inventory["identity"]["machine_id_hash"],
        "network_hash": inventory["identity"]["network_hash"],
        "machine": inventory["hardware"]["machine"],
        "os": inventory["software"]["operating_system"],
        "root": str(ROOT_DIR),
    }
    inventory["fingerprint"] = _hash(json.dumps(fingerprint_basis, sort_keys=True))[:32]
    return inventory


def load_registered_device() -> dict[str, Any]:
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_registered_device(record: dict[str, Any]) -> dict[str, Any]:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(REGISTRY_PATH)
    return record


def _stable_identity_matches(current: dict[str, Any], registered: dict[str, Any]) -> bool:
    current_identity = current.get("identity", {})
    registered_identity = registered.get("identity", {})
    current_machine_id = current_identity.get("machine_id_hash", "")
    registered_machine_id = registered_identity.get("machine_id_hash", "")
    if (
        current_machine_id
        and registered_machine_id
        and current_machine_id != "unavailable"
        and current_machine_id == registered_machine_id
    ):
        return True

    stable_pairs = (
        (current_identity.get("hostname"), registered_identity.get("hostname")),
        (current_identity.get("user"), registered_identity.get("user")),
        (current.get("hardware", {}).get("machine"), registered.get("hardware", {}).get("machine")),
        (
            current.get("software", {}).get("operating_system"),
            registered.get("software", {}).get("operating_system"),
        ),
    )
    return all(left and left == right for left, right in stable_pairs)


def register_current_device(label: str = "primary") -> dict[str, Any]:
    inventory = collect_device_inventory()
    record = {
        "label": label.strip() or "primary",
        "registered_at": _utc_now(),
        "trusted": True,
        "inventory": inventory,
    }
    return _write_registered_device(record)


def auto_detect_and_register_device(label: str = "primary") -> dict[str, Any]:
    current = collect_device_inventory()
    registered = load_registered_device()
    current_fp = current.get("fingerprint", "")
    registered_inventory = registered.get("inventory", {})
    registered_fp = registered_inventory.get("fingerprint", "")

    if not registered:
        record = {
            "label": label.strip() or "primary",
            "registered_at": _utc_now(),
            "trusted": True,
            "inventory": current,
            "auto_detected": True,
        }
        return {
            "action": "registered",
            "trusted": True,
            "record": _write_registered_device(record),
            "current_fingerprint": current_fp,
            "registered_fingerprint": current_fp,
        }

    if registered_fp == current_fp:
        return {
            "action": "already_trusted",
            "trusted": True,
            "record": registered,
            "current_fingerprint": current_fp,
            "registered_fingerprint": registered_fp,
        }

    if _stable_identity_matches(current, registered_inventory):
        updated = dict(registered)
        updated["label"] = (label.strip() if label.strip() else updated.get("label")) or "primary"
        updated["trusted"] = True
        updated["last_auto_detected_at"] = _utc_now()
        updated["previous_fingerprint"] = registered_fp
        updated["inventory"] = current
        return {
            "action": "refreshed",
            "trusted": True,
            "record": _write_registered_device(updated),
            "current_fingerprint": current_fp,
            "registered_fingerprint": current_fp,
            "previous_fingerprint": registered_fp,
        }

    updated = dict(registered)
    updated["label"] = (label.strip() if label.strip() else updated.get("label")) or "primary"
    updated["trusted"] = True
    updated["last_auto_detected_at"] = _utc_now()
    updated["previous_fingerprint"] = registered_fp
    updated["previous_identity"] = registered_inventory.get("identity", {})
    updated["inventory"] = current
    return {
        "action": "replaced",
        "trusted": True,
        "record": _write_registered_device(updated),
        "current_fingerprint": current_fp,
        "registered_fingerprint": current_fp,
        "previous_fingerprint": registered_fp,
    }


def verify_current_device() -> dict[str, Any]:
    current = collect_device_inventory()
    registered = load_registered_device()
    registered_inventory = registered.get("inventory", {})
    registered_fp = registered_inventory.get("fingerprint", "")
    current_fp = current.get("fingerprint", "")
    exact_match = bool(registered_fp and registered_fp == current_fp)
    stable_match = bool(registered and _stable_identity_matches(current, registered_inventory))
    return {
        "registered": bool(registered),
        "trusted": exact_match or stable_match,
        "trust_match": "fingerprint" if exact_match else "stable_identity" if stable_match else "none",
        "current_fingerprint": current_fp,
        "registered_fingerprint": registered_fp,
        "label": registered.get("label", ""),
        "registered_at": registered.get("registered_at", ""),
        "current": current,
        "registered_record": registered,
    }


def format_device_report(detail: bool = False) -> str:
    verification = verify_current_device()
    current = verification["current"]
    lines = [
        "Device Trust Report",
        "-------------------",
        f"Registered: {verification['registered']}",
        f"Trusted: {verification['trusted']}",
        f"Trust Match: {verification['trust_match']}",
        f"Label: {verification.get('label') or 'none'}",
        f"Fingerprint: {verification['current_fingerprint']}",
        f"Host: {current['identity']['hostname']}",
        f"User: {current['identity']['user']}",
        f"OS: {current['software']['operating_system']}",
        f"Machine: {current['hardware']['machine']}",
        f"CPU cores: {current['hardware']['cpu_cores']}",
        f"Memory: {current['hardware']['total_memory']}",
        f"Local IP: {current['network']['local_ip']}",
        f"Connectivity: {current['network']['connectivity']}",
    ]
    if detail:
        lines.extend([
            "",
            "Software packages:",
            json.dumps(current["software"]["packages"], indent=2, ensure_ascii=False),
            "",
            "Network interfaces:",
            json.dumps(current["network"]["interfaces"], indent=2, ensure_ascii=False),
            "",
            "Environment:",
            json.dumps(current["environment"], indent=2, ensure_ascii=False),
        ])
    return "\n".join(lines)


def format_device_section(section: str) -> str:
    verification = verify_current_device()
    current = verification["current"]
    section_key = section.strip().lower()
    titles = {
        "hardware": "Device Hardware Report",
        "software": "Device Software Report",
        "network": "Device Network Report",
        "environment": "Device Environment Report",
    }
    if section_key not in titles:
        return "Unknown device detail section."

    lines = [
        titles[section_key],
        "-" * len(titles[section_key]),
        f"Trusted: {verification['trusted']}",
        f"Trust Match: {verification['trust_match']}",
        f"Fingerprint: {verification['current_fingerprint']}",
        "",
    ]
    lines.append(json.dumps(current[section_key], indent=2, ensure_ascii=False))
    if section_key == "environment":
        lines.append("")
        lines.append("Secret values are not shown or stored.")
    return "\n".join(lines)
