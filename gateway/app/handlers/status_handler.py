"""
Status handler: returns concise system health for message channels.
"""

from __future__ import annotations

import asyncio
import os
import platform
import socket
from datetime import datetime, timezone
from typing import Any


def _read_uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            seconds = float(f.read().split()[0])
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"
    except OSError:
        return "unknown"


def _cpu_percent() -> str:
    try:
        import psutil  # type: ignore
        return f"{psutil.cpu_percent(interval=0.1):.0f}%"
    except ImportError:
        pass
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        vals = list(map(int, line.split()[1:]))
        idle = vals[3]
        total = sum(vals)
        return f"~{100 - int(idle * 100 / total)}%"
    except OSError:
        return "n/a"


def _memory() -> str:
    try:
        import psutil  # type: ignore
        m = psutil.virtual_memory()
        return f"{m.percent:.0f}% ({m.available // 1024 // 1024}MB free)"
    except ImportError:
        pass
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")
                info[k.strip()] = int(v.split()[0])
        total = info.get("MemTotal", 0)
        avail = info.get("MemAvailable", info.get("MemFree", 0))
        pct = int((total - avail) * 100 / total) if total else 0
        return f"~{pct}% ({avail // 1024}MB free)"
    except OSError:
        return "n/a"


def _disk() -> str:
    try:
        import shutil
        usage = shutil.disk_usage("/")
        pct = int(usage.used * 100 / usage.total)
        free_gb = usage.free // (1024 ** 3)
        return f"{pct}% used ({free_gb}GB free)"
    except OSError:
        return "n/a"


def _temperature() -> str:
    paths = [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/class/hwmon/hwmon0/temp1_input",
    ]
    for p in paths:
        try:
            with open(p) as f:
                raw = int(f.read().strip())
            temp = raw / 1000.0 if raw > 1000 else float(raw)
            return f"{temp:.1f}°C"
        except OSError:
            continue
    return "n/a"


async def _internet_reachable() -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("8.8.8.8", 53), timeout=2
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def handle_status(**kwargs: Any) -> str:
    internet = await _internet_reachable()
    lines = [
        f"Host: {socket.gethostname()}",
        f"OS: {platform.system()} {platform.release()}",
        f"Uptime: {_read_uptime()}",
        f"CPU: {_cpu_percent()}",
        f"Memory: {_memory()}",
        f"Disk: {_disk()}",
        f"Temp: {_temperature()}",
        f"Internet: {'✓' if internet else '✗'}",
        f"Time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
    ]
    return "\n".join(lines)
