"""Persistent network history store (SQLite, zero external deps).

Keeps a long-term, low-rate time series of key metrics so the UI can show
24h / 7d / 30d trends — the "insight" layer the in-memory live rings can't
provide (those are wiped on restart and only cover the last couple of minutes).

Design:
  - One writer (the background sampler thread) + many readers.
  - SQLite in WAL mode → concurrent reads never block the writer.
  - A single module lock guards all DB access (simplest correct approach).
  - Retention bounded (default 30 days), pruned opportunistically.

The sampler is decoupled from the server: ``start_sampl`` takes a ``provider``
callable that returns the current snapshot dict, so this module never imports
the HTTP layer (no circular dependency).
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path

from .paths import DATA_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get(
    "NETVISUAL_HISTORY_DB", str(DATA_DIR / "netvisual_history.db")))

RETENTION_DAYS = int(os.environ.get("NETVISUAL_HISTORY_DAYS", "30"))
SAMPLE_INTERVAL = int(os.environ.get("NETVISUAL_HISTORY_INTERVAL", "30"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
  ts          INTEGER NOT NULL,
  rx_bps      REAL    NOT NULL DEFAULT 0,
  tx_bps      REAL    NOT NULL DEFAULT 0,
  recv_total  REAL    NOT NULL DEFAULT 0,
  sent_total  REAL    NOT NULL DEFAULT 0,
  devices     INTEGER NOT NULL DEFAULT 0,
  connections INTEGER NOT NULL DEFAULT 0,
  tcp_est     INTEGER NOT NULL DEFAULT 0,
  lat_ms      REAL,
  gw_up       INTEGER,
  PRIMARY KEY (ts)
);
CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics (ts);

CREATE TABLE IF NOT EXISTS device_ips (
  ts INTEGER NOT NULL,
  ip TEXT    NOT NULL,
  kind TEXT,
  PRIMARY KEY (ts, ip)
);
CREATE INDEX IF NOT EXISTS idx_devips_ts ON device_ips (ts);

CREATE TABLE IF NOT EXISTS known_devices (
  mac         TEXT PRIMARY KEY,
  ip          TEXT,
  vendor      TEXT,
  first_seen  INTEGER NOT NULL,
  last_seen   INTEGER NOT NULL,
  trusted     INTEGER NOT NULL DEFAULT 1
);
"""

_lock = threading.Lock()
_sampl = None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init() -> None:
    """Create the schema if needed (idempotent)."""
    with _lock, _connect() as conn:
        conn.executescript(SCHEMA)


def record(snap: dict) -> None:
    """Insert one sample (dedup on ts). Missing keys default to 0/NULL."""
    ts = int(snap.get("ts", int(time.time())))
    row = (
        ts,
        float(snap.get("rx_bps", 0) or 0),
        float(snap.get("tx_bps", 0) or 0),
        float(snap.get("recv_total", 0) or 0),
        float(snap.get("sent_total", 0) or 0),
        int(snap.get("devices", 0) or 0),
        int(snap.get("connections", 0) or 0),
        int(snap.get("tcp_est", 0) or 0),
        snap.get("lat_ms"),
        (1 if snap.get("gw_up") else (0 if snap.get("gw_up") is False else None)),
    )
    ips = snap.get("ips") or []
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO metrics (ts, rx_bps, tx_bps, recv_total, sent_total,"
            " devices, connections, tcp_est, lat_ms, gw_up) VALUES (?,?,?,?,?,?,?,?,?,?)",
            row,
        )
        if ips:
            conn.executemany(
                "INSERT OR REPLACE INTO device_ips (ts, ip, kind) VALUES (?,?,?)",
                [(ts, str(d["ip"]), d.get("kind")) for d in ips if d.get("ip")],
            )


def prune(days: int | None = None) -> int:
    """Delete samples older than ``days``. Returns metrics rows removed."""
    days = RETENTION_DAYS if days is None else days
    cutoff = int(time.time()) - int(days * 86400)
    with _lock, _connect() as conn:
        cur = conn.execute("DELETE FROM metrics WHERE ts < ?", (cutoff,))
        removed = cur.rowcount
        conn.execute("DELETE FROM device_ips WHERE ts < ?", (cutoff,))
        return removed


def _fetch(seconds: int) -> list[tuple]:
    cutoff = int(time.time()) - seconds
    with _lock, _connect() as conn:
        cur = conn.execute(
            "SELECT ts, rx_bps, tx_bps, recv_total, sent_total, devices, connections,"
            " tcp_est, lat_ms, gw_up FROM metrics WHERE ts >= ? ORDER BY ts ASC",
            (cutoff,),
        )
        return cur.fetchall()


def query_range(seconds: int, buckets: int = 180) -> list[dict]:
    """Return the series for the last ``seconds``, downsampled to ≤ ``buckets``."""
    rows = _fetch(seconds)
    if not rows:
        return []
    b = 1 if len(rows) <= buckets else -(-len(rows) // buckets)  # ceil
    out: list[dict] = []
    for i in range(0, len(rows), b):
        chunk = rows[i:i + b]
        n = len(chunk)
        rx = sum(r[1] for r in chunk) / n
        tx = sum(r[2] for r in chunk) / n
        devices = sum(r[5] for r in chunk) / n
        connections = sum(r[6] for r in chunk) / n
        tcp = sum(r[7] for r in chunk) / n
        lats = [r[8] for r in chunk if r[8] is not None]
        lat = (sum(lats) / len(lats)) if lats else None
        out.append({
            "ts": chunk[0][0],
            "rx": round(rx, 1), "tx": round(tx, 1),
            "devices": round(devices, 1), "connections": round(connections, 1),
            "tcp": round(tcp, 1),
            "lat": round(lat, 1) if lat is not None else None,
        })
    return out


def stats_range(seconds: int) -> dict:
    """Aggregate stats over the last ``seconds`` for the KPI strip."""
    rows = _fetch(seconds)
    if not rows:
        return {
            "range_s": seconds, "points": 0, "span_s": 0,
            "data_rx_bytes": 0, "data_tx_bytes": 0,
            "rx_peak": 0, "tx_peak": 0, "rx_avg": 0, "tx_avg": 0,
            "lat_avg": None, "lat_peak": None, "lat_min": None,
            "devices_peak": 0, "devices_avg": 0,
            "connections_peak": 0, "gw_up_pct": None,
            "first_ts": None, "last_ts": None,
        }
    first, last = rows[0], rows[-1]
    n = len(rows)
    rx = [r[1] for r in rows]
    tx = [r[2] for r in rows]
    data_rx = max(0, last[3] - first[3])
    data_tx = max(0, last[4] - first[4])
    if data_rx == 0 and data_tx == 0:
        span = last[0] - first[0]
        data_rx = sum(rx) * (span / max(n, 1))
        data_tx = sum(tx) * (span / max(n, 1))
    lats = [r[8] for r in rows if r[8] is not None]
    gw = [r[9] for r in rows if r[9] is not None]
    return {
        "range_s": seconds,
        "points": n,
        "span_s": last[0] - first[0],
        "data_rx_bytes": int(data_rx), "data_tx_bytes": int(data_tx),
        "rx_peak": max(rx), "tx_peak": max(tx),
        "rx_avg": round(sum(rx) / n, 1), "tx_avg": round(sum(tx) / n, 1),
        "lat_avg": round(sum(lats) / len(lats), 1) if lats else None,
        "lat_peak": max(lats) if lats else None,
        "lat_min": min(lats) if lats else None,
        "devices_peak": max(r[5] for r in rows),
        "devices_avg": round(sum(r[5] for r in rows) / n, 1),
        "connections_peak": max(r[6] for r in rows),
        "gw_up_pct": round(100.0 * sum(1 for g in gw if g) / len(gw), 1) if gw else None,
        "first_ts": first[0], "last_ts": last[0],
    }


def info() -> dict:
    now = int(time.time())
    with _lock, _connect() as conn:
        rows, first, last = conn.execute(
            "SELECT COUNT(*), MIN(ts), MAX(ts) FROM metrics").fetchone()
        devs = conn.execute("SELECT COUNT(DISTINCT ip) FROM device_ips").fetchone()[0]
    return {
        "rows": rows, "first_ts": first, "last_ts": last,
        "span_days": round((last - first) / 86400, 3) if first and last else 0,
        "retention_days": RETENTION_DAYS,
        "interval_s": SAMPLE_INTERVAL,
        "sampling": bool(_sampl and _sampl.is_alive()),
        "tracked_ips": devs, "db_path": str(DB_PATH),
    }


def clear() -> int:
    with _lock, _connect() as conn:
        cur = conn.execute("DELETE FROM metrics")
        removed = cur.rowcount
        conn.execute("DELETE FROM device_ips")
        return removed


# ===========================================================================
# Stage-1 analytics: status/uptime, device events, baselines, anomaly, alerts
# ===========================================================================

def status_range(seconds: int) -> dict:
    """Gateway reachability over the last ``seconds`` (up % + segments)."""
    rows = _fetch(seconds)
    if not rows:
        return {"up_pct": None, "segments": [], "total_down_s": 0, "points": 0}
    segs: list[dict] = []
    for ts, *_ , gw in rows:
        state = "up" if gw else ("down" if gw is not None else "unknown")
        if segs and segs[-1]["state"] == state:
            segs[-1]["end_ts"] = ts
            segs[-1]["seconds"] = ts - segs[-1]["start_ts"]
        else:
            segs.append({"state": state, "start_ts": ts, "end_ts": ts, "seconds": 0})
    gw_known = [r[9] for r in rows if r[9] is not None]
    up = sum(1 for g in gw_known if g)
    down_s = sum(s["seconds"] for s in segs if s["state"] == "down")
    return {
        "up_pct": round(100.0 * up / len(gw_known), 1) if gw_known else None,
        "segments": segs, "total_down_s": down_s, "points": len(rows),
    }


def device_events(seconds: int, limit: int = 100) -> dict:
    """Detect IPs that appeared / disappeared within the window."""
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT ts, ip FROM device_ips WHERE ts >= ? ORDER BY ts ASC, ip ASC",
            (int(time.time()) - seconds,)).fetchall()
    by_ts: dict[int, set] = {}
    for ts, ip in rows:
        by_ts.setdefault(ts, set()).add(ip)
    ts_sorted = sorted(by_ts)
    events: list[dict] = []
    for i in range(1, len(ts_sorted)):
        prev, cur = by_ts[ts_sorted[i - 1]], by_ts[ts_sorted[i]]
        for ip in sorted(cur - prev):
            events.append({"event": "appeared", "ip": ip, "ts": ts_sorted[i]})
        for ip in sorted(prev - cur):
            events.append({"event": "disappeared", "ip": ip, "ts": ts_sorted[i]})
    events.sort(key=lambda e: e["ts"], reverse=True)
    with _lock, _connect() as conn:
        pres = conn.execute(
            "SELECT ip, MIN(ts), MAX(ts), COUNT(DISTINCT ts) "
            "FROM device_ips WHERE ts >= ? GROUP BY ip ORDER BY MAX(ts) DESC",
            (int(time.time()) - seconds,)).fetchall()
    return {
        "events": events[:limit], "event_count": len(events),
        "presence": [{"ip": ip, "first_seen": fs, "last_seen": ls, "samples_online": n}
                     for (ip, fs, ls, n) in pres],
    }


def device_presence(seconds: int) -> list[dict]:
    """Per-IP online/absence summary over the window."""
    with _lock, _connect() as conn:
        total_samples = conn.execute(
            "SELECT COUNT(DISTINCT ts) FROM metrics WHERE ts >= ?",
            (int(time.time()) - seconds,)).fetchone()[0]
        pres = conn.execute(
            "SELECT ip, MIN(ts), MAX(ts), COUNT(DISTINCT ts) "
            "FROM device_ips WHERE ts >= ? GROUP BY ip ORDER BY MAX(ts) DESC",
            (int(time.time()) - seconds,)).fetchall()
    now = int(time.time())
    out = []
    for ip, fs, ls, n in pres:
        online_pct = round(100.0 * n / total_samples, 1) if total_samples else 0.0
        out.append({
            "ip": ip, "first_seen": fs, "last_seen": ls,
            "samples_online": n, "online_pct": online_pct,
            "currently_present": (now - ls) <= max(SAMPLE_INTERVAL * 3, 90),
        })
    return out


def baseline(seconds: int, metric: str = "rx_bps") -> dict:
    """Average value per hour-of-day over the window."""
    col = metric if metric in ("rx_bps", "tx_bps") else "rx_bps"
    rows = _fetch(seconds)
    if not rows:
        return {"metric": col, "by_hour": [], "avg_all": 0, "points": 0}
    idx = {"rx_bps": 1, "tx_bps": 2}[col]
    buckets: dict[int, list[float]] = {}
    for r in rows:
        buckets.setdefault((r[0] // 3600) % 24, []).append(r[idx])
    by_hour = [
        {"hour": h, "avg": round(sum(v) / len(v), 1), "samples": len(v)}
        for h, v in sorted(buckets.items())
    ]
    allv = [r[idx] for r in rows]
    return {
        "metric": col, "by_hour": by_hour,
        "avg_all": round(sum(allv) / len(allv), 1), "points": len(rows),
    }


def anomaly(value: float, seconds: int, metric: str = "rx_bps", z: float = 3.0) -> dict:
    """Z-score of ``value`` against the historical distribution in the window."""
    col = metric if metric in ("rx_bps", "tx_bps") else "rx_bps"
    rows = _fetch(seconds)
    idx = {"rx_bps": 1, "tx_bps": 2}[col]
    if len(rows) < 5:
        return {"is_anomaly": False, "z": None, "mean": None, "std": None,
                "points": len(rows), "threshold": z, "value": value}
    vals = [r[idx] for r in rows]
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = var ** 0.5
    zs = 0.0 if std == 0 else (value - mean) / std
    return {
        "is_anomaly": abs(zs) >= z, "z": round(zs, 2),
        "mean": round(mean, 1), "std": round(std, 1),
        "points": len(rows), "threshold": z, "value": value,
    }


def alerts(seconds: int, thresholds: dict | None = None) -> dict:
    """Evaluate configured alert thresholds over the recent window."""
    from . import config as _cfg  # local import: keeps DAG acyclic
    th = dict(thresholds or {})
    cfg = _cfg.alerts()
    for k in ("gw_down_seconds", "gw_latency_ms", "bandwidth_rx_bps",
              "bandwidth_tx_bps", "anomaly_z"):
        if th.get(k) is None:
            th[k] = cfg.get(k)
    rows = _fetch(seconds)
    if not rows:
        return {"alerts": [], "last": {}, "checked": False, "points": 0}
    last = rows[-1]
    out: list[dict] = []
    now = int(time.time())

    if last[9] == 0:
        down_since = last[0]
        for r in reversed(rows):
            if r[9] == 0:
                down_since = r[0]
            else:
                break
        down_for = last[0] - down_since
        if down_for >= th.get("gw_down_seconds", 90):
            out.append({"id": "gw_down", "severity": "critical", "metric": "gateway",
                        "value": "down", "threshold": f">={th.get('gw_down_seconds',90)}s",
                        "detail": f"gateway down for {down_for}s", "ts": last[0]})

    last_lat = last[8]
    if last_lat is not None and th.get("gw_latency_ms") is not None:
        if last_lat > th["gw_latency_ms"]:
            out.append({"id": "gw_latency", "severity": "warning", "metric": "latency_ms",
                        "value": last_lat, "threshold": f">{th['gw_latency_ms']}ms",
                        "detail": f"gateway latency {last_lat}ms", "ts": now})

    rx_peak = max(r[1] for r in rows)
    tx_peak = max(r[2] for r in rows)
    if th.get("bandwidth_rx_bps") is not None and rx_peak > th["bandwidth_rx_bps"]:
        out.append({"id": "bw_rx", "severity": "warning", "metric": "rx_bps",
                    "value": rx_peak, "threshold": f">{th['bandwidth_rx_bps']}/s",
                    "detail": f"RX peak {rx_peak}/s", "ts": now})
    if th.get("bandwidth_tx_bps") is not None and tx_peak > th["bandwidth_tx_bps"]:
        out.append({"id": "bw_tx", "severity": "warning", "metric": "tx_bps",
                    "value": tx_peak, "threshold": f">{th['bandwidth_tx_bps']}/s",
                    "detail": f"TX peak {tx_peak}/s", "ts": now})

    z_th = th.get("anomaly_z", 3.0)
    a = anomaly(last[1], seconds, "rx_bps", z_th)
    if a.get("is_anomaly"):
        out.append({"id": "rx_anomaly", "severity": "warning", "metric": "rx_bps",
                    "value": last[1], "threshold": f"z>={z_th}",
                    "detail": f"RX z-score {a['z']} (mean {a['mean']})", "ts": now})

    sev_rank = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda a: (sev_rank.get(a["severity"], 3), a["id"]))
    return {
        "alerts": out, "active": len(out),
        "last": {"ts": last[0], "rx_bps": last[1], "tx_bps": last[2],
                 "lat_ms": last[8],
                 "gw_up": bool(last[9]) if last[9] is not None else None},
        "checked": True, "points": len(rows),
    }


def start_sampl(provider, interval: int | None = None,
                prune_every: int = 240) -> threading.Thread:
    """Launch the daemon sampler (idempotent). ``provider`` returns a snapshot dict."""
    global _sampl
    if _sampl and _sampl.is_alive():
        return _sampl
    init()
    interval = SAMPLE_INTERVAL if interval is None else max(5, int(interval))

    def loop():
        tick = 0
        while True:
            try:
                snap = provider() or {}
                snap.setdefault("ts", int(time.time()))
                record(snap)
            except Exception:
                pass  # never let a bad snapshot kill the sampler
            tick += 1
            if tick % prune_every == 0:
                try:
                    prune()
                except Exception:
                    pass
            time.sleep(interval)

    _sampl = threading.Thread(target=loop, name="history-sampl", daemon=True)
    _sampl.start()
    return _sampl


def track_known_devices(devices: list[dict]) -> tuple[list[dict], list[dict]]:
    """Enrich devices with is_new status, persist to DB, and return (enriched_devs, new_devs)."""
    now = int(time.time())
    new_devices = []
    enriched = []
    
    with _lock, _connect() as conn:
        cursor = conn.cursor()
        for d in devices:
            mac = (d.get("mac") or "").upper().strip()
            ip = d.get("ip", "").strip()
            vendor = d.get("vendor", "") or ""
            
            if not mac or mac in ("FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00") or mac.startswith("01:00:5E"):
                d_copy = dict(d)
                d_copy["is_new"] = False
                enriched.append(d_copy)
                continue
                
            cursor.execute("SELECT first_seen, trusted FROM known_devices WHERE mac = ?", (mac,))
            row = cursor.fetchone()
            d_copy = dict(d)
            if row is None:
                # Brand new device discovered!
                cursor.execute(
                    "INSERT INTO known_devices (mac, ip, vendor, first_seen, last_seen, trusted) VALUES (?,?,?,?,?,?)",
                    (mac, ip, vendor, now, now, 0)
                )
                d_copy["is_new"] = True
                d_copy["trusted"] = False
                new_devices.append(d_copy)
            else:
                cursor.execute("UPDATE known_devices SET last_seen = ?, ip = ? WHERE mac = ?", (now, ip, mac))
                d_copy["is_new"] = (row[1] == 0)
                d_copy["trusted"] = bool(row[1])
            enriched.append(d_copy)
        conn.commit()
        
    return enriched, new_devices


def acknowledge_device(mac: str) -> bool:
    """Mark a device MAC address as trusted/acknowledged."""
    if not mac:
        return False
    mac = mac.upper().strip()
    with _lock, _connect() as conn:
        conn.execute("UPDATE known_devices SET trusted = 1 WHERE mac = ?", (mac,))
        conn.commit()
    return True

