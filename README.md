# NetVisual A+ v6

<div align="center">

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg?logo=windows)](https://github.com/gaipunkx/NetVisual)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![Zero External Deps](https://img.shields.io/badge/Runtime%20Dependencies-Zero%20External%20Deps-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Release-v6.0-8A2BE2.svg)]()

**The Modular, High-Performance, Zero-Dependency Windows Network Intelligence & Cyber Suite.**

[Features](#-key-feature-suites) • [Quick Start](#-quick-start) • [Cyber AI Copilot](#-cyber-ai-copilot--agent-tools) • [Architecture](#-project-architecture) • [Building & Packaging](#-building-from-source) • [Security](#-security--port-release-guarantee)

</div>

---

A single click gives you an instant, GPU-accelerated cyber dashboard covering your entire LAN and WAN: your local PC, gateway, discovered neighbors, live packet sniffer, speed test, Wi-Fi spectrum optimizer, threat inspector,  profile switcher, and 30-day time-series analytics.

```
┌─────────────┐        ┌─────────────┐        ┌──────────────────┐
│   This PC   │◄──────►│   Gateway   │◄──────►│  Neighbour 1..N  │
│  (127.0.0.1)│        │ (192.168.x) │        │   (ARP + Ping)   │
└─────────────┘        └─────────────┘        └──────────────────┘
        │
        ├── 🌍 World Geo Map (OpenStreetMap tiles + GPU Cyber Dark styling, 100% Free)
        ├── 🛡️ Threat & Security Inspector (Socket audit, DNS leak check, WHOIS/ASN)
        ├── 🤖 Cyber AI Copilot (LLM Agent with live network tools & natural language)
        ├── ⚡ Built-in Speed Test & QoS (Multi-stream DL/UL, Ping, Jitter, Loss)
        ├── 📶 Wi-Fi Analyzer & Spectrum Optimizer (2.4/5GHz channel congestion)
        ├── 🎛️ NetProfiles & DNS Switcher (Cloudflare, Quad9, AdGuard, 1-Click Repair, WOL)
        ├── 🦈 Live Packet Sniffer (Hex/ASCII dump , PCAP export)
        └── 📈 Persistent Trends & Time-Series History (SQLite-backed, 30-day retention)
```

---

## 🚀 Key Feature Suites

### 1. 📊 Live Network Monitor
- **Real-Time Bandwidth Gauges**: SVG cyber radial speedometers tracking Rx / Tx throughput, totals, peak and rolling average.
- **Gateway Latency & Jitter**: Continuous ping latency with jitter graphs.
- **Top Talkers by Process**: Aggregated socket telemetry grouped by executable.
- **Remote Peer Grouping**: Classification of active sockets (Local LAN vs. External WAN endpoints).

### 2. 🤖 Cyber AI Copilot & Agent Tools
- **Multi-Model Intelligence**: Native support for **Google Gemini**, **Anthropic Claude**, **OpenAI GPT-4o**, and local **Ollama** endpoints.
- **Autonomous Tool Execution**: The AI copilot directly executes local diagnostic routines:
  - `run_security_audit`: Scans listening sockets for malware/miner risks.
  - `search_web`: Live search for CVEs, port signatures, and security advisories.
  - `check_ip`: Autonomous WHOIS and AlienVault threat intelligence lookup.
  - `check_dns_leaks`: Verifies DNS security posture and encryption leaks.
  - `run_ping` & `run_traceroute`: Network latency and hop diagnosis.
  - `set_dns`: 1-click DNS switcher tool called by voice/text.
- **Bilingual Interface**: Native, bidirectional-safe Hebrew (RTL) & English output.

### 3. 🦈 Live Packet Sniffer & Protocol Analyzer (Wireshark Suite)
- **Real-Time Packet Stream**: Live capture of TCP, UDP, ICMP, DNS, TLS/HTTPS, and HTTP packets without external packet drivers.
- **Follow TCP / UDP Stream**: Reassembles full client/server conversation payloads in a dual-color stream dialogue.
- **IP Conversations Matrix**: Aggregated 2-way traffic flows (Packets A⇄B, Bytes A⇄B, total volume).
- **Wireshark BPF Filter Chips**: 1-click filtering (`🟢 SYN Only`, `🔍 DNS`, `🔒 TLS / HTTPS`, `🌐 HTTP`, `⚠️ UDP`, `📡 ICMP Ping`).
- **2-Pane Packet Inspector**:
  - Structured packet tree breakdown (Ethernet, IPv4, Transport Header, Flags, Payload).
  - Monospace 16-byte aligned Hex & ASCII dump viewer.
- **PCAP Export**: 1-click **⬇ Export .PCAP** generating standard Libpcap binary captures compatible with Wireshark.

### 4. 🌍 World Geo Map (Zero-API-Key, 100% Free)
- **Real-Time Geolocation**: Maps all active external internet connections in real time.
- **Curved Flight Paths**: Geodesic arcs connecting your host PC to destination servers worldwide.
- **Open Global Tiles**: Powered by OpenStreetMap without requiring API keys or third-party accounts.
- **GPU-Accelerated Cyber Dark Styling**: Sleek, high-contrast dark theme rendered in real time.
- **Multiple Map Layers**: Cyber Dark Neon, Standard OpenStreetMap, Esri World Satellite Imagery, and Humanitarian (HOT).

### 5. 🛡️ Threat & Security Inspector
- **Active Socket Audit**: Scans open TCP/UDP sockets against known vulnerability signatures (malware, miners, remote shells, open SMB/Telnet).
- **DNS Leak Posture Checker**: Tests upstream DNS resolver privacy and leak vectors.
- **WHOIS & ASN Resolver**: In-depth IP ownership and reputation inspection.
- **Security Grade Metric**: Instant global network security grading (e.g. `A+`, 100/100).

### 6. ⚡ Built-in Speed Test & QoS Analyzer
- **Multi-Stream Benchmarking**: Fast Download and Upload benchmarks against globally distributed edge CDNs.
- **Precision QoS Metrics**: Measures **Ping Latency (ms)**, **Jitter (ms)**, and **Packet Loss (%)**.
- **Cyber Speedometer**: Neon radial needle animations with live throughput progress.

### 7. 📶 Wi-Fi Analyzer & Spectrum Advisor
- **Wireless Adapter Inspection**: SSID, BSSID, RSSI Signal (% and dBm), 802.11ax/ac radio standard, WPA security, and link synchronization rates.
- **Channel Congestion Histograms**: Real-time channel utilization for both **2.4 GHz** (Channels 1–11) and **5 GHz** (Channels 36–165).
- **Smart Spectrum Advisor**: Algorithmic recommendation for the cleanest, least crowded Wi-Fi channels in your area.

### 8. 📁 Net Profiles Manager (NetSetMan Visual Suite)
- **Visual Profile Tabs**: Manage multiple profiles (`#1 Home`, `#2 Work (Static IP)`, `#3 Gaming (Low-Ping)`, `#4 Shield & AdBlock`) with 1-click tab switching.
- **Full IP & Gateway Control**: Switch seamlessly between **Automatic (DHCP)** and **Static IP** (IP Address, Subnet Mask, Gateway) per profile.
- **DNS Server Management**: Automatic DHCP DNS or **Manual DNS** (Preferred & Alternate DNS) with 1-click presets (Cloudflare, Quad9, AdGuard, Google).
- **System Proxy & Notes**: Custom notes, proxy IP:Port, profile icons, and automatic adapter binding.

### 9. 🧰 Network Tools & System Repair
- **1-Click Fast DNS Switcher**: Instant switching between Cloudflare (1.1.1.1), Quad9 (9.9.9.9), AdGuard DNS, Google (8.8.8.8), or Automatic (DHCP) with automatic cache flush.
- **Windows Hosts Anti-Telemetry Shield**: Curated anti-telemetry & adblock shield blocking diagnostic telemetry, tracking beacons, and malware domains in `C:\Windows\System32\drivers\etc\hosts`.
- **1-Click Network Repair & Flush**: Clears DNS cache, purges ARP neighbor tables, and re-registers network endpoints.
- **Wake-on-LAN (WOL)**: Sends magic packets (UDP port 9) to wake remote computers or NAS units.

### 10. 📈 Persistent Trends & Time-Series History
- **SQLite Storage**: Efficient, low-overhead time-series metrics engine.
- **Customizable Intervals**: Analyze trends across **6h, 24h, 7d, and 30d**.
- **Host Discovery Timeline**: Audit log of device joins and disconnections over time.

---

## 🏃 Quick Start

### Prerequisites
- Windows 10 or Windows 11 (64-bit)
- Python 3.10+ (if running from source)

### Running from Source
```powershell
# Clone repository
git clone https://github.com/gaipunkx/NetVisual.git
cd NetVisual

# Run in console mode
python -m netvisual.server

# Or run in Windows System Tray mode (double-click run.bat or run via CLI)
python netvisual_app.py --tray
```

The web dashboard opens automatically at `http://127.0.0.1:8730`.

---

## 🏗 Project Architecture

```
NetVisual/
├── netvisual/                  # Core Python backend package
│   ├── api/                    # API endpoints & route handlers
│   ├── parsers/                # OS command & telemetry parsers (arp, netstat, ipconfig)
│   ├── probes/                 # Background samplers & network probes
│   ├── state/                  # Ring-buffer state & synchronization
│   ├── agent_tools.py          # Cyber AI Copilot tools (audit, whois, search)
│   ├── history.py              # SQLite persistent time-series storage
│   ├── llm.py                  # Multi-provider LLM client (Gemini, Claude, OpenAI)
│   ├── netprofiles.py          # NetSetMan-style profile switcher & presets
│   ├── paths.py                # Stable cross-platform path resolution
│   ├── security.py             # Socket vulnerability & threat intelligence engine
│   ├── server.py               # Lightweight HTTP server & endpoint router
│   ├── sniffer.py              # Live raw packet sniffer & PCAP generator
│   ├── speedtest.py            # Multi-stream CDN throughput benchmark
│   ├── tray.py                 # Windows system tray integration (pystray)
│   └── wifi.py                 # Wireless interface & spectrum analyzer
├── static/                     # Single-page web dashboard
│   ├── index.html              # Cyber UI dashboard layout & modals
│   ├── app.js                  # Frontend controllers, charts & WebSocket/polling
│   ├── layout.css              # Glassmorphic layout & animations
│   └── theme.css               # Cyber Neon, Matrix, Dracula & OLED themes
├── tests/                      # Comprehensive test suite
│   ├── test_security.py        # Input sanitation & threat test suite
│   ├── test_http.py            # API endpoint integration tests
│   └── test_v3_history.py      # SQLite store & trend analysis tests
├── tools/                      # Build & icon generation utilities
├── installer.iss               # Official Inno Setup script
├── NetVisual.spec              # PyInstaller standalone configuration
├── netvisual_app.py            # Root launcher entrypoint
├── pyproject.toml              # Project metadata & configuration
└── run.bat                     # Windows tray mode desktop launcher
```

---

## 📦 Building from Source

### Standalone Executable (PyInstaller)
To compile NetVisual into a single, zero-dependency Windows `.exe`:
```powershell
pip install pyinstaller pystray pillow
pyinstaller NetVisual.spec
```
The resulting binary is saved to `dist/NetVisual.exe`.

### Windows Installer (Inno Setup)
To build the official graphical Windows Setup installer:
1. Compile the executable using PyInstaller above.
2. Compile the installer script using the Inno Setup compiler:
```powershell
iscc installer.iss
```
The output installer will be created in `dist/installer/NetVisual-v6-Setup.exe`.

---

## 🔒 Security & Port Release Guarantee

- **Deterministic Port Release**: The server uses a deterministic shutdown mechanism that closes listening sockets immediately upon exit.
- **Single-Instance Guard**: Attempting to launch a second instance automatically focuses the existing browser dashboard instead of failing with port conflicts.
- **Localhost Isolation**: The HTTP server binds exclusively to `127.0.0.1`.
- **Command Injection Firewall**: All user inputs (IPs, hostnames, ports) are strictly validated via `safety.py` before execution.

---

## 📄 License & Attribution

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

- **Leaflet.js**: BSD-2-Clause License
- **OpenStreetMap Tiles**: © OpenStreetMap contributors (ODbL)
- **Google Fonts (Inter / JetBrains Mono)**: SIL Open Font License 1.1
