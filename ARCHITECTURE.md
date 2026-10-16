# NetVisual A+ v6 — Architecture

> A modular, **zero-dependency / standalone** Windows network intelligence suite. Built with a strict layered DAG architecture, deterministic lifecycle management, real-time packet sniffing, speed testing, wireless spectrum analysis, and profile management.

---

## 🏛️ Layered Architecture & Import Graph

NetVisual A+ is organized into four strictly segregated architectural tiers. Dependencies strictly point downwards (higher layers depend only on layers beneath them, with zero cyclic imports):

```
                 ┌──────────────────────────────────────────────────────────┐
   UI (Browser)  │        static/index.html · app.js · style.css            │
                 └────────────────────────────┬─────────────────────────────┘
                                              │ HTTP REST (36+ Endpoints)
                 ┌────────────────────────────▼─────────────────────────────┐
   API Tier      │  api/handler.py   (REST routing & serialization)         │
                 │  api/rangeutil.py (Time range parser, pure)              │
                 │  api/snapshot.py  (Telemetry sampler & event evaluator)  │
                 └────────────────────────────┬─────────────────────────────┘
                                              │
                 ┌────────────────────────────▼─────────────────────────────┐
   Feature &     │  security.py   (Threat analysis, DNS leak, WHOIS)        │
   Composition   │  speedtest.py  (Multi-stream DL/UL, ping, jitter, loss)  │
   Tier          │  wifi.py       (WLAN interface & spectrum advisor)       │
                 │  netprofiles.py(1-Click DNS switcher, repair, WOL)       │
                 │  hostsmanager.py(Windows hosts & anti-telemetry shield)  │
                 │  sniffer.py    (Live packet dissection, hex, PCAP)       │
                 │  geo.py        (Batch Geo-IP lookup & coordinates)       │
                 │  notifier.py   (Windows toast alerts)                    │
                 │  summary.py · topology.py · peers.py · probes.py         │
                 └────────────────────────────┬─────────────────────────────┘
                                              │
                 ┌────────────────────────────▼─────────────────────────────┐
   Services Tier │  selfinfo · ping · dns · traceroute · portscan           │
                 │  history.py (SQLite WAL time series & stats)             │
                 │  state/ (traffic · activity · latency · sweep rings)     │
                 └────────────────────────────┬─────────────────────────────┘
                                              │
                 ┌────────────────────────────▼─────────────────────────────┐
   Foundation    │  runner · safety · cache · oui · paths · config          │
   Tier          │  parsers/ (ipconfig · arp · routes · netstat · tasklist) │
                 └──────────────────────────────────────────────────────────┘
```

---

## 📦 Package Module Map

| Path | Responsibility | Pure? |
|------|----------------|-------|
| `netvisual/__init__.py` | Package metadata & version | yes |
| `netvisual/paths.py` | Resolves ROOT, STATIC, DATA, CONFIG, LOG (frozen PyInstaller aware) | yes |
| `netvisual/runner.py` | `run()` (allow-list) + `run_list()` (no-shell) subprocess wrappers | — (I/O) |
| `netvisual/safety.py` | `safe_ip`, `safe_host`, `safe_port` input sanitization firewall | **yes** |
| `netvisual/cache.py` | Thread-safe TTL memoization + `clear()` for `POST /api/refresh` | — |
| `netvisual/oui.py` | MAC OUI → Hardware Vendor resolution | yes |
| `netvisual/parsers/*.py` | Independent pure parsers for Windows CLI tools | **yes** |
| `netvisual/security.py` | Threat audit, port signature analysis, DNS leak & WHOIS | — (I/O) |
| `netvisual/speedtest.py` | Multi-stream network bandwidth & QoS benchmarking | — (I/O) |
| `netvisual/wifi.py` | Wireless interface inspection, channel congestion & advisor | — (I/O) |
| `netvisual/netprofiles.py`| 1-Click DNS presets, network repair, adapter reboot & WOL | — (I/O) |
| `netvisual/hostsmanager.py`| Windows hosts file & anti-telemetry adblock shield manager | — (I/O) |
| `netvisual/sniffer.py` | Live packet sniffer, Follow Stream, conversations & PCAP exporter | — (I/O) |
| `netvisual/explainer.py` | Smart AI network health synthesizer & diagnostic explainer | — |
| `netvisual/geo.py` | In-memory cached batch Geo-IP resolution | — (I/O) |
| `netvisual/notifier.py` | Native Windows desktop toast notification engine | — (I/O) |
| `netvisual/history.py` | SQLite (WAL) 30-day time-series store & analytics | — (I/O) |
| `netvisual/probes.py` | TTL-cached hardware & network probe aggregators | — |
| `netvisual/topology.py` | Subnet device graph builder & ping-sweep coordinator | — |
| `netvisual/peers.py` | Remote peers & top talkers process aggregators | partly |
| `netvisual/summary.py` | Master `GET /api/summary` aggregator | — |
| `netvisual/api/handler.py`| HTTP REST request routing & dispatching | — |
| `netvisual/api/snapshot.py`| Periodic snapshot builder feeding history & notification triggers | — |
| `netvisual/tray.py` | Windows system tray taskbar integration via `pystray` | — |
| `netvisual/server.py` | Server bootstrap, `make_stoppable` one-shot port release guard | — |

---

## 🛡️ Security & Input Safety Model

1. **Subprocess Isolation**:
   - `runner.run()` only executes exact strings present in the hardcoded `ALLOWED_RAW` set.
   - `runner.run_list()` uses structured argument lists with `shell=False` to prevent shell metacharacter injection.
2. **Input Validation Firewall**:
   - All query parameters passing to network diagnostics pass through `safety.safe_ip()`, `safety.safe_host()`, or `safety.safe_port()`.
3. **Path Traversal Protection**:
   - The static asset handler resolves canonical paths and verifies that all requested resources remain strictly inside the `STATIC/` directory.
4. **Localhost Binding**:
   - HTTP server binds strictly to `127.0.0.1`.

---

## ⚡ Deterministic Lifecycle & Port Release (`make_stoppable`)

NetVisual implements a zero-leakage lifecycle contract in `netvisual/server.py:make_stoppable()`:

- **One-Shot Teardown Guard**: Protects against double-shutdown hangs in Python's `ThreadingHTTPServer.shutdown()`.
- **Daemon Thread Teardown**: Runs socket closure in a dedicated daemon thread with a 3.0s join timeout.
- **Immediate Socket Close**: Directly calls `server_close()` to free TCP port `8730` immediately on any termination path (Tray Exit, Ctrl+C, or Taskbar close).
- **Single-Instance Handler**: If an existing instance is already running on port `8730`, new invocations open the existing dashboard in the default browser and exit cleanly.

---

## 🦈 Packet Dissection & PCAP Generation

The `netvisual/sniffer.py` module operates as follows:
1. Captures IP traffic (using Windows raw sockets or active connection flow reconstruction).
2. Dissects IPv4 headers (IHL, Total Length, TTL, Protocol).
3. Dissects TCP (Sequence, Ack, Flags: SYN, ACK, FIN, RST, PSH, URG) and UDP headers.
4. Identifies application protocols (DNS, TLS/HTTPS, HTTP, QUIC, NTP, mDNS, SSDP, SMB).
5. Generates 16-byte aligned Hex & ASCII dumps.
6. Builds standard Libpcap binary files (`0xa1b2c3d4` global header + per-packet records) exportable directly to Wireshark.

---

## 🧪 Verification & Test Suite

The test suite ensures 100% integrity across all modules:
- `tests/test_backend_v2.py`: Backend probes & parsers.
- `tests/test_css.py`: CSS token integrity and syntax.
- `tests/test_dom.py`: Full DOM ID parity between `static/index.html` and `static/app.js`.
- `tests/test_security.py`: Port scan, safety firewall, and threat rules.
- `tests/test_v3_history.py`: SQLite time-series storage and range query math.
- `tests/test_tray_stop.py`: End-to-end tray shutdown & immediate port re-bind verification.
