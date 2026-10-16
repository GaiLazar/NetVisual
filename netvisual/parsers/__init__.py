"""Output parsers: raw CLI text → structured dicts.

Each parser lives in its own file and is pure (no I/O, no subprocess) so it can
be unit-tested against captured sample output without touching the network.
Locale-proof: parsers match numeric patterns (MACs, dotted-quads, numbers)
rather than English/Hebrew label words where possible.
"""
from __future__ import annotations

from .ipconfig import parse_ipconfig
from .arp import parse_arp
from .routes import parse_routes
from .netstat import parse_netstat, parse_netstat_e
from .tasklist import parse_tasklist_csv

__all__ = [
    "parse_ipconfig",
    "parse_arp",
    "parse_routes",
    "parse_netstat",
    "parse_netstat_e",
    "parse_tasklist_csv",
]
