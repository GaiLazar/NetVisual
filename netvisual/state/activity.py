"""Activity feed: a ring buffer of notable network events.

Populated by the probe layer (device up/down, listening-port open/close,
bandwidth spikes) and surfaced by ``GET /api/activity``. Thread-safe.
"""
from __future__ import annotations

import threading
import time

_ACTIVITY_MAX = 200

_activity: list[dict] = []
_activity_lock = threading.Lock()
_last_devices: set = set()
_last_listen: set = set()


def add(kind: str, msg: str, level: str = "info") -> None:
    """Append one event; trims the ring to the most recent ``_ACTIVITY_MAX``."""
    with _activity_lock:
        _activity.append({"ts": time.time(), "kind": kind, "level": level, "msg": msg})
        if len(_activity) > _ACTIVITY_MAX:
            _activity[:] = _activity[-_ACTIVITY_MAX:]


def feed() -> list[dict]:
    """A copy of the current event ring (oldest first)."""
    with _activity_lock:
        return list(_activity)


def record_devices(devices) -> None:
    """Diff the current device IP set against the previous; log new/lost."""
    global _last_devices
    cur = set(devices)
    with _activity_lock:
        prev = set(_last_devices)
        _last_devices = cur
    for ip in sorted(cur - prev):
        add("device_up", f"device appeared: {ip}", "good")
    for ip in sorted(prev - cur):
        add("device_down", f"device disappeared: {ip}", "warn")


def record_listening(ports) -> None:
    """Diff the current listening-port set against the previous; log changes."""
    global _last_listen
    cur = set(ports)
    with _activity_lock:
        prev = set(_last_listen)
        _last_listen = cur
    for p in sorted(cur - prev):
        add("port_open", f"new listening port: {p}", "info")
    for p in sorted(prev - cur):
        add("port_closed", f"port closed: {p}", "info")
