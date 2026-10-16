"""Live in-memory state: bandwidth ring, activity feed, latency ring, sweep.

These are the mutable, time-varying pieces that the v3 monolith kept as
module-level globals. Here each lives in its own module with a single source
of truth for its lock, so behaviour is identical to v3 but inspectable and
testable in isolation.

Public surface (new canonical names):
    activity_add / activity_feed / record_devices / record_listening
    latency_sample / last_reachability
    sweep_begin / sweep_end / sweep_status / sweep_tick
    traffic_sample / traffic_history

v3 aliases (re-exported for the ``server`` compat shim):
    sample_latency, sample_traffic
"""
from __future__ import annotations

from . import activity, latency, sweep, traffic
from .activity import add as activity_add, feed as activity_feed
from .activity import record_devices, record_listening
from .latency import last_reachability, sample as latency_sample
from .sweep import begin as sweep_begin, end as sweep_end
from .sweep import status as sweep_status, tick as sweep_tick
from .traffic import history as traffic_history, sample as traffic_sample

# v3 aliases (tests and user scripts may reference these names)
sample_latency = latency_sample
sample_traffic = traffic_sample

__all__ = [
    "activity", "latency", "sweep", "traffic",
    "activity_add", "activity_feed", "record_devices", "record_listening",
    "last_reachability", "latency_sample",
    "sweep_begin", "sweep_end", "sweep_status", "sweep_tick",
    "traffic_history", "traffic_sample",
    # v3 aliases
    "sample_latency", "sample_traffic",
]
