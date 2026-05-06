#!/usr/bin/env python3

import getpass
import json
import os
import platform
import socket
from datetime import datetime, timezone


def format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{value} B"


def get_memory_info() -> tuple[str, str]:
    page_size = os.sysconf("SC_PAGE_SIZE")
    total_pages = os.sysconf("SC_PHYS_PAGES")
    available_pages = os.sysconf("SC_AVPHYS_PAGES")

    total = page_size * total_pages
    available = page_size * available_pages
    return format_bytes(total), format_bytes(available)


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "Unavailable"


def get_connectivity_status() -> str:
    return "Connected" if get_local_ip() != "Unavailable" else "Offline"


def get_system_info() -> dict[str, str]:
    uname = platform.uname()
    total_memory, available_memory = get_memory_info()

    return {
        "user": getpass.getuser(),
        "hostname": socket.gethostname(),
        "operating_system": f"{uname.system} {uname.release}",
        "os_version": uname.version,
        "machine": uname.machine,
        "processor": uname.processor or platform.processor() or "Unavailable",
        "python_version": platform.python_version(),
        "current_directory": os.getcwd(),
        "local_time": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "utc_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "cpu_cores": str(os.cpu_count() or "Unavailable"),
        "total_memory": total_memory,
        "available_memory": available_memory,
        "local_ip": get_local_ip(),
        "connectivity": get_connectivity_status(),
    }


def print_system_info() -> None:
    info = get_system_info()
    labels = {
        "user": "User",
        "hostname": "Hostname",
        "operating_system": "Operating System",
        "os_version": "OS Version",
        "machine": "Machine",
        "processor": "Processor",
        "python_version": "Python Version",
        "current_directory": "Current Directory",
        "local_time": "Local Time",
        "utc_time": "UTC Time",
        "cpu_cores": "CPU Cores",
        "total_memory": "Total Memory",
        "available_memory": "Available Memory",
        "local_ip": "Local IP",
        "connectivity": "Connectivity",
    }

    print("System Information")
    print("-" * 18)
    for key, label in labels.items():
        print(f"{label}: {info[key]}")


def print_system_info_json() -> None:
    print(json.dumps(get_system_info(), indent=2))


if __name__ == "__main__":
    print_system_info()
