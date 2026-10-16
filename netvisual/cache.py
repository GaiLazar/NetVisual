"""Thread-safe TTL cache for probe results.

Probes are expensive (each spawns a subprocess) and the UI polls every couple
of seconds, so we memoise per key with a TTL. The cache also stamps every value
with ``elapsed_ms`` so the UI can show how long the real probe took.

Defaults:
    TTL      = 20s  (general probes)
    TOPO_TTL = 45s  (topology: ARP + optional sweep is heavier)
"""
from __future__ import annotations

import threading
import time

TTL = 20
TOPO_TTL = 45

_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()


def get(key: str, producer, ttl: int = TTL) -> dict:
    """Return the cached value for ``key`` if fresh, else run ``producer()``.

    ``producer`` must return a dict (or anything — it is wrapped in ``{"value":}``).
    The stored copy is annotated with ``elapsed_ms`` (probe wall time).
    """
    with _cache_lock:
        e = _cache.get(key)
        if e and (time.time() - e["t"]) < ttl:
            return e["v"]
    t0 = time.time()
    v = producer()
    if not isinstance(v, dict):
        v = {"value": v}
    stored = dict(v)
    stored["elapsed_ms"] = int((time.time() - t0) * 1000)
    with _cache_lock:
        _cache[key] = {"t": time.time(), "v": stored}
    return stored


def clear() -> None:
    """Drop all cached probes (used by ``POST /api/refresh``)."""
    with _cache_lock:
        _cache.clear()
