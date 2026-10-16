"""Range-string parser for the history/trend endpoints.

Accepts ``'24h' | '7d' | '30d' | '6h' | '1w'`` → ``(seconds, buckets)``.
``buckets`` is a sensible downsample target for the chart (smaller window →
finer points), capped at 360 to keep payloads small.
"""
from __future__ import annotations


def parse_range(raw: str) -> tuple[int, int] | None:
    """Parse a range string into ``(seconds, buckets)``; ``None`` if invalid."""
    r = (raw or "").strip().lower()
    if not r:
        return None
    unit = r[-1]
    try:
        num = int(r[:-1])
    except (ValueError, IndexError):
        return None
    if unit == "h":
        return max(1, num) * 3600, min(360, max(24, num * 6))
    if unit == "d":
        return max(1, num) * 86400, min(360, max(60, num * 24))
    if unit == "w":
        return max(1, num) * 604800, min(360, max(60, num * 168))
    return None
