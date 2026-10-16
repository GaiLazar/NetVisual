"""DNS resolution via ``nslookup`` (arg-list, injection-safe).

Two lookups:
  - ``dns_lookup(host)``  → A record (name → IP addresses)
  - ``reverse_dns(ip)``   → PTR record (IP → name), stdlib resolver first,
                           ``nslookup -q=px`` fallback.
"""
from __future__ import annotations

import re
import socket

from .runner import run_list
from .safety import safe_host, safe_ip

_ADDR_RE = re.compile(r"Address(?:es)?\s*[:\s]+([\d.]+)")
_NAME_RE = re.compile(r"Name\s*:\s*(\S+)")


def dns_lookup(host: str) -> dict:
    """Resolve ``host`` to a list of IP addresses (plus CNAME if present)."""
    if not safe_host(host):
        return {"host": host, "answers": [], "cname": None, "error": "invalid host"}
    code, out = run_list(["nslookup", host.strip()], timeout=8)
    answers = _ADDR_RE.findall(out)
    cname = _NAME_RE.search(out)
    return {"host": host, "answers": answers,
            "cname": cname.group(1) if cname else None}


def reverse_dns(ip: str) -> dict:
    """Resolve ``ip`` to a hostname. stdlib resolver first, nslookup fallback."""
    if not safe_ip(ip):
        return {"ip": ip, "name": None, "found": False, "error": "invalid IP"}
    ip = ip.strip()
    name = None
    try:
        name, _aliases, _addrs = socket.gethostbyaddr(ip)
    except Exception:
        name = None
    if not name:
        code, out = run_list(["nslookup", "-q=px", ip], timeout=8)
        m = _NAME_RE.search(out)
        if m:
            name = m.group(1)
    if name:
        name = name.rstrip(".")
    return {"ip": ip, "name": name, "found": bool(name)}
