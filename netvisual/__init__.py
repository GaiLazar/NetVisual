"""NetVisual A+ v4 — a modular, zero-dependency Windows network visualizer.

The monolithic ``server.py`` of v3 is decomposed into this package so that each
concern (running commands, parsing output, holding live state, probing, routing)
lives in its own small module. See ARCHITECTURE.md for the full design.

Public entry point:
    from netvisual.server import main

Layers (import DAG, bottom → top, acyclic):
    paths / runner / safety / cache / parsers / oui     (no deps)
    selfinfo / ping / dns / traceroute / portscan / state (leaf services)
    probes / topology / peers                            (compose the above)
    summary / api                                        (compose probes)
    server.main                                          (entry point)
"""
from __future__ import annotations

__all__ = ["__version__", "VERSION"]

#: Application version string (also reported by ``--version``).
__version__ = "6.0.0"
VERSION = __version__
