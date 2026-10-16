"""NetVisual runtime configuration.

Resolution order (highest wins):
  1. Environment variables  (NETVISUAL_*)
  2. netvisual.json in the project root (user-editable, survives restart)
  3. Built-in defaults

Keeps every tunable in one place so changing one value re-tunes the whole app.
"""
from __future__ import annotations

import json
import os

from .paths import CONFIG_PATH

DEFAULTS = {
    "history": {
        "retention_days": 30,
        "interval_seconds": 30,
        "max_points": 360,
    },
    "alerts": {
        "enabled": True,
        "gw_down_seconds": 90,
        "gw_latency_ms": 200,
        "bandwidth_rx_bps": 50_000_000,
        "bandwidth_tx_bps": 50_000_000,
        "anomaly_z": 3.0,
    },
    "ui": {
        "live_refresh_ms": 2000,
        "trends_refresh_ms": 60000,
    },
}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if v is None:
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _env_over() -> dict:
    def _int(name, cast=None):
        raw = os.environ.get(name)
        if raw is None or raw == "":
            return None
        try:
            return cast(int(raw)) if cast else int(raw)
        except ValueError:
            return None

    def _float(name):
        raw = os.environ.get(name)
        if raw is None or raw == "":
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    return {
        "history": {
            "retention_days": _int("NETVISUAL_HISTORY_DAYS"),
            "interval_seconds": _int("NETVISUAL_HISTORY_INTERVAL"),
            "max_points": _int("NETVISUAL_HISTORY_MAX_POINTS"),
        },
        "alerts": {
            "enabled": (os.environ.get("NETVISUAL_ALERTS_ENABLED") not in ("0", "false", "no"))
                    if "NETVISUAL_ALERTS_ENABLED" in os.environ else None,
            "gw_down_seconds": _int("NETVISUAL_ALERT_GW_DOWN_SECONDS"),
            "gw_latency_ms": _int("NETVISUAL_ALERT_GW_LATENCY_MS"),
            "bandwidth_rx_bps": _int("NETVISUAL_ALERT_BW_RX_BPS"),
            "bandwidth_tx_bps": _int("NETVISUAL_ALERT_BW_TX_BPS"),
            "anomaly_z": _float("NETVISUAL_ALERT_ANOMALY_Z"),
        },
    }


def _load_file() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


_cache = None
_cache_key = None


def _env_key() -> tuple:
    return tuple(os.environ.get(n) for n in (
        "NETVISUAL_HISTORY_DAYS", "NETVISUAL_HISTORY_INTERVAL", "NETVISUAL_HISTORY_MAX_POINTS",
        "NETVISUAL_ALERTS_ENABLED", "NETVISUAL_ALERT_GW_DOWN_SECONDS",
        "NETVISUAL_ALERT_GW_LATENCY_MS", "NETVISUAL_ALERT_BW_RX_BPS",
        "NETVISUAL_ALERT_BW_TX_BPS", "NETVISUAL_ALERT_ANOMALY_Z",
    ))


def load() -> dict:
    """Return the merged config. Re-reads when the file or env values change."""
    global _cache, _cache_key
    mtime = None
    try:
        mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else None
    except OSError:
        pass
    key = (mtime, _env_key())
    if _cache is not None and key == _cache_key:
        return _cache
    merged = _deep_merge(_deep_merge(DEFAULTS, _load_file()), _env_over())
    _cache, _cache_key = merged, key
    return merged


def alerts() -> dict:
    return load()["alerts"]


def history_cfg() -> dict:
    return load()["history"]


def write_defaults() -> str:
    """Create netvisual.json with defaults if missing. Returns the path."""
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return str(CONFIG_PATH)
