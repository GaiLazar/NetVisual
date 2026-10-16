"""Route tracing via ``tracert`` (arg-list, injection-safe)."""
from __future__ import annotations

import re

from .runner import run_list
from .safety import safe_host

_HOP_RE = re.compile(r"\s*(\d+)\s+(.*)")


def traceroute(host: str, maxhops: int = 15) -> list[dict]:
    """Trace the path to ``host``; return ``[{"hop","raw"}, ...]``."""
    if not safe_host(host):
        return []
    code, out = run_list(["tracert", "-d", "-h", str(int(maxhops)), host.strip()],
                         timeout=int(maxhops) * 3)
    hops: list[dict] = []
    for line in out.splitlines():
        m = _HOP_RE.match(line)
        if not m:
            continue
        hops.append({"hop": int(m.group(1)), "raw": m.group(2).strip()})
    return hops
