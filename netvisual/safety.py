"""Input validation — the injection firewall.

Every value that flows into ``run_list`` (ping/dns/tracert/portscan) must first
pass one of these checks. They block shell metacharacters and malformed input
so that ``run_list``'s "no shell" property is never the only line of defence.

Pure, dependency-free, and unit-testable in isolation (see tests/test_safety.py).
"""
from __future__ import annotations

import ipaddress
import re

# Plausible hostname / IPv4 / IPv6-literal charset. No spaces, no metacharacters.
_HOST_RE = re.compile(r"[A-Za-z0-9._\-]+")


def safe_ip(ip: str) -> bool:
    """True iff ``ip`` is a syntactically valid IPv4 address."""
    if not isinstance(ip, str):
        return False
    try:
        ipaddress.IPv4Address(ip.strip())
        return True
    except (ValueError, ipaddress.AddressValueError):
        return False


def safe_host(h: str) -> bool:
    """True iff ``h`` is a plausible hostname or IP literal.

    Rejects empty strings, anything >253 chars, embedded whitespace, and any
    character outside ``[A-Za-z0-9._-]``. This is what keeps ``nslookup`` and
    ``tracert`` from ever seeing a shell metacharacter.
    """
    if not isinstance(h, str):
        return False
    h = h.strip()
    if not h or len(h) > 253:
        return False
    if any(ch.isspace() for ch in h):
        return False
    return _HOST_RE.fullmatch(h) is not None


def safe_port(p) -> int | None:
    """Coerce ``p`` (int or numeric string) to a valid TCP/UDP port, else None."""
    try:
        n = int(p)
    except (TypeError, ValueError):
        return None
    if 1 <= n <= 65535:
        return n
    return None
