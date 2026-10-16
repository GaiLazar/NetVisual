"""Parse ``route print`` (IPv4 table) into route dicts.

Recognises the 5-column main IPv4 table:
    Network Destination | Netmask | Gateway | Interface | Metric

Dedupe on (dest, netmask, gateway) since Windows prints the same route in
multiple sections (physical vs. tunnel).
"""
from __future__ import annotations

import re

_DOTTED = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def parse_routes(text: str) -> list[dict]:
    """Return a de-duplicated list of IPv4 route rows.

    Each row: ``{"dest","netmask","gateway","iface","metric"}``.
    """
    routes: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        dest, netmask, gateway, iface, metric = parts[:5]
        if not (_DOTTED.match(dest) and _DOTTED.match(netmask)
                and (_DOTTED.match(gateway) or gateway == "On-link")):
            continue
        key = (dest, netmask, gateway)
        if key in seen:
            continue
        seen.add(key)
        routes.append({"dest": dest, "netmask": netmask, "gateway": gateway,
                       "iface": iface, "metric": metric})
    return routes
