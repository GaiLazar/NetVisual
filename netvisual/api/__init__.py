"""REST API layer — routes, HTTP handler, range parser, history snapshot.

Split out of the v3 monolith:
  - ``rangeutil.py`` — ``parse_range`` helper (pure)
  - ``snapshot.py``  — the ``history_snapshot`` provider for the background sampler
  - ``handler.py``   — the ``BaseHTTPRequestHandler`` subclass (all endpoints)
"""
from __future__ import annotations

from .handler import Handler
from .rangeutil import parse_range
from .snapshot import history_snapshot

__all__ = ["Handler", "parse_range", "history_snapshot"]
