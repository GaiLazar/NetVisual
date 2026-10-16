"""Compatibility shim — exposes the v3 ``server`` module surface on the v4 package.

v3 tests (and any user script) do ``import server`` and call module-level
functions like ``s.ping``, ``s.lookup_vendor``, ``s.sweep_status``. In v4 those
functions live in the :mod:`netvisual` package. This thin shim re-exports them
at the ``server`` namespace so the existing test suite runs unmodified, while
the real code stays modular under ``netvisual/``.

This file contains NO logic — it is a re-export surface only.
"""
from __future__ import annotations

from netvisual import __version__  # noqa: F401
from netvisual import (  # noqa: F401  (submodules available as server.<name>)
    cache, config, history, oui, paths, ping, peers, portscan, probes,
    runner, safety, selfinfo, state, summary, topology, traceroute,
)

# v3 module-level names that tests and scripts expect at ``server.*``
from netvisual.ping import ping  # noqa: F401
from netvisual.dns import dns_lookup, reverse_dns  # noqa: F401
from netvisual.traceroute import traceroute  # noqa: F401
from netvisual.portscan import portscan, COMMON_PORTS  # noqa: F401
from netvisual.selfinfo import own_ip, self_netinfo  # noqa: F401
from netvisual.oui import lookup_vendor  # noqa: F401
from netvisual.peers import (  # noqa: F401
    _remote_host, group_remote_peers, remote_peers, top_talkers,
)
from netvisual.safety import safe_ip, safe_host, safe_port  # noqa: F401
from netvisual.runner import run, run_list  # noqa: F401
from netvisual.state import (  # noqa: F401
    activity_feed, last_reachability, sample_latency, sweep_status,
    sample_traffic, traffic_history,
)
# v3 private recorder names (tests use s._record_devices / s._record_listening)
from netvisual.state import record_devices as _record_devices  # noqa: F401
from netvisual.state import record_listening as _record_listening  # noqa: F401
from netvisual.probes import (  # noqa: F401
    process_names, probe_arp, probe_connections, probe_interfaces,
    probe_routes, probe_traffic,
)
from netvisual.parsers import (  # noqa: F401
    parse_ipconfig, parse_arp, parse_routes,
    parse_netstat, parse_netstat_e, parse_tasklist_csv,
)
from netvisual.summary import summary  # noqa: F401
from netvisual.api.handler import ALLOWED_RAW  # noqa: F401


def probe_topology(sweep: bool = False) -> dict:
    """v3 name → the modular topology builder (cached; sweep=True is fresh)."""
    from netvisual import topology as _t
    return _t.probe(sweep=sweep)


def build_topology(sweep: bool = False) -> dict:
    """Alias kept for scripts that use the v3 ``build_topology`` name."""
    return probe_topology(sweep)


def main():
    """Entry point (equivalent to ``python -m netvisual.server``).

    Lets v3-style ``python server.py`` launches keep working against v4.
    """
    from netvisual.server import main as _main
    _main()


if __name__ == "__main__":
    main()
