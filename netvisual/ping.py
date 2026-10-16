"""ICMP reachability via ``ping`` (arg-list, injection-safe)."""
from __future__ import annotations

import re

from .runner import run_list
from .safety import safe_ip

_MS_RE = re.compile(r"time[=<](\d+)ms", re.IGNORECASE)
_TTL_RE = re.compile(r"TTL=(\d+)", re.IGNORECASE)

def ping(ip: str, count: int = 2) -> dict:
    """Ping ``ip`` and report reachability / average latency / loss / os.

    Returns ``{"ip","reachable","avg_ms","loss_pct","ttl","os_guess"}``
    """
    if not safe_ip(ip):
        return {"ip": ip, "reachable": False, "avg_ms": None, "loss_pct": None,
                "ttl": None, "os_guess": None, "error": "invalid IP"}
    ip = ip.strip()
    code, out = run_list(["ping", "-n", str(int(count)), ip], timeout=8)
    ms_vals = _MS_RE.findall(out)
    ttl_vals = _TTL_RE.findall(out)
    loss_m = (re.search(r"(\d+)% loss", out, re.IGNORECASE)
              or re.search(r"(\d+)% packet loss", out, re.IGNORECASE))
              
    ttl = int(ttl_vals[0]) if ttl_vals else None
    os_guess = None
    if ttl:
        if ttl <= 64: os_guess = "Linux/Mac"
        elif ttl <= 128: os_guess = "Windows"
        else: os_guess = "Network App"

    return {
        "ip": ip,
        "reachable": code == 0 and len(ms_vals) > 0,
        "avg_ms": round(sum(map(int, ms_vals)) / len(ms_vals), 1) if ms_vals else None,
        "loss_pct": int(loss_m.group(1)) if loss_m else None,
        "ttl": ttl,
        "os_guess": os_guess
    }
