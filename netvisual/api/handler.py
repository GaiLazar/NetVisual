"""HTTP request handler — the full REST surface.

This is the only module that knows about URLs. It composes the probe/topology/
peer/summary/history layers and serves ``static/``. Faithful port of the v3
``Handler`` (all 29 GET endpoints + the POST refresh), now calling into the
modular package instead of module-level functions.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: F401
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import cache, explainer, export, firewall, geo, history, hostsmanager, netprofiles, notifier, peers, portscan, probes, security, sniffer, speedtest, summary, topology, wifi, llm, agent_tools
from ..dns import dns_lookup, reverse_dns
from ..ping import ping
from ..runner import run
from ..state import (
    activity_feed, latency_sample, sweep_status, traffic_sample,
)
from ..traceroute import traceroute
from .rangeutil import parse_range

# Fixed, read-only commands the ``/api/raw`` console may run (injection-proof
# because the exact string must be in this set).
ALLOWED_RAW = {
    "ipconfig /all", "ipconfig /displaydns",
    "arp -a", "route print", "netstat -ano", "netstat -s", "netstat -e",
    "systeminfo", "nbtstat -n", "netstat -r",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "NetVisual/6.0"

    def log_message(self, *a):  # quiet
        pass

    def _safe_send(self, fn):
        """Run a response-write fn, swallowing client-abort errors quietly."""
        try:
            fn()
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode()

        def _w():
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        self._safe_send(_w)

    def _file(self, path: Path, ctype: str):
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return

        def _w():
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(data)
        self._safe_send(_w)

    def _send_bytes(self, data: bytes, ctype: str, code=200, extra_headers: dict | None = None):
        def _w():
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            if extra_headers:
                for k, v in extra_headers.items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        self._safe_send(_w)

    # -- helpers to keep do_GET readable ------------------------------------ #
    def _q(self, q, name, default=None):
        return q.get(name, [default])[0]

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                raw = self.rfile.read(length)
                return json.loads(raw.decode("utf-8"))
        except Exception:
            pass
        return None

    def _range(self, q, default="24h"):
        """Return (pr, seconds) or None if the range is invalid."""
        pr = self._q(q, "range", default)
        rng = parse_range(pr)
        if rng is None:
            return None
        return pr, rng[0]

    def do_GET(self):
        from ..paths import STATIC  # local import keeps module import cheap
        u = urlparse(self.path)
        p = u.path
        q = parse_qs(u.query)
        try:
            if p in ("/", ""):
                return self._file(STATIC / "index.html", "text/html; charset=utf-8")
            if p.startswith("/static/"):
                name = p[len("/static/"):].strip("/")
                target = (STATIC / name).resolve()
                if not (target.is_relative_to(STATIC.resolve()) or target == STATIC.resolve()):
                    return self._json({"error": "forbidden"}, 403)
                ctype = ("text/html; charset=utf-8" if name.endswith(".html") or name == ""
                         else "text/css; charset=utf-8" if name.endswith(".css")
                         else "application/javascript; charset=utf-8" if name.endswith(".js")
                         else "application/octet-stream")
                return self._file(target, ctype)

            # ---- core probes -------------------------------------------- #
            if p == "/api/summary":
                return self._json(summary.summary())
            if p == "/api/interfaces":
                return self._json(probes.probe_interfaces())
            if p == "/api/arp":
                return self._json(probes.probe_arp())
            if p == "/api/routes":
                return self._json(probes.probe_routes())
            if p == "/api/connections":
                return self._json(probes.probe_connections())
            if p == "/api/topology":
                sweep = self._q(q, "sweep", "0") in ("1", "true", "yes")
                topo = topology.probe(sweep=sweep)
                neighbors = topo.get("neighbors", [])
                enriched, new_devs = history.track_known_devices(neighbors)
                topo["neighbors"] = enriched
                if new_devs:
                    notifier.evaluate_events(enriched, topo.get("gateway", {}).get("up"))
                return self._json(topo)
            if p == "/api/ping":
                return self._json(ping(self._q(q, "ip", "127.0.0.1")))
            if p == "/api/dns":
                return self._json(dns_lookup(self._q(q, "host", "google.com")))
            if p == "/api/traceroute":
                h = self._q(q, "host", "8.8.8.8")
                return self._json({"host": h, "hops": traceroute(h)})
            if p == "/api/raw":
                cmd = (self._q(q, "cmd", "ipconfig /all") or "").strip()
                if cmd not in ALLOWED_RAW:
                    return self._json({"error": "command not allowed",
                                       "allowed": sorted(ALLOWED_RAW)}, 400)
                code, out = run(cmd, 20)
                return self._json({"cmd": cmd, "code": code, "output": out})
            if p == "/api/commands":
                return self._json({"allowed": sorted(ALLOWED_RAW)})
            if p == "/api/traffic":
                return self._json(probes.probe_traffic())
            if p == "/api/activity":
                return self._json({"events": activity_feed()[::-1]})
            if p == "/api/processes":
                return self._json({"processes": probes.process_names()})
            if p == "/api/top-talkers":
                return self._json({"top": peers.top_talkers(limit=self._lim(q, "n", 8))})
            if p == "/api/peers":
                return self._json({"peers": peers.remote_peers(limit=self._lim(q, "n", 10))})
            if p == "/api/portscan":
                ip = self._q(q, "ip", "127.0.0.1")
                ports = self._q(q, "ports", None)
                tval = float(self._q(q, "timeout", None)) if self._q(q, "timeout", None) else None
                plist = None
                if ports:
                    plist = [int(x) for x in ports.replace(",", " ").split() if x.isdigit()]
                return self._json(portscan.portscan(ip, ports=plist,
                                                    timeout=tval if tval else 0.6))
            if p == "/api/ptr":
                return self._json(reverse_dns(self._q(q, "ip", "127.0.0.1")))
            if p == "/api/latency":
                return self._json(latency_sample())
            if p == "/api/service-latency":
                from ..servicematrix import check_services
                return self._json({"services": check_services()})
            if p == "/api/scan-status":
                return self._json(sweep_status())
            if p in ("/api/geomap", "/api/geo-connections"):
                return self._json(geo.get_geo_connections())
            if p == "/api/security/audit":
                return self._json(security.audit_security())
            if p == "/api/security/whois":
                return self._json(security.query_whois(self._q(q, "ip", "1.1.1.1")))
            if p == "/api/security/threat-intel":
                return self._json(security.check_threat_intel(self._q(q, "ip", "1.1.1.1")))
            if p == "/api/security/dns-leak":
                return self._json(security.check_dns_leaks())
            if p == "/api/ai/chat":
                body = self._read_json_body() if self.command == "POST" else {}
                return self._json(llm.chat(body))
            if p == "/api/ai/action":
                body = self._read_json_body() if self.command == "POST" else {}
                tool_name = body.get("tool", "")
                args = body.get("args", {})
                return self._json(agent_tools.execute_tool_call(tool_name, args))
            if p == "/api/ai/test":
                body = self._read_json_body() if self.command == "POST" else {}
                return self._json(llm.test_connection(body))
            if p == "/api/speedtest/start":
                return self._json({"started": speedtest.start_speedtest()})
            if p == "/api/speedtest/status":
                return self._json(speedtest.get_status())
            if p == "/api/wifi":
                wdata = wifi.get_wifi_details()
                current_ssid = wdata.get("ssid")
                if current_ssid:
                    auto_res = netprofiles.auto_switch_ssid_profile(current_ssid)
                    if auto_res:
                        wdata["auto_switched_profile"] = auto_res
                return self._json(wdata)
            if p == "/api/notifications/settings":
                return self._json(notifier.load_settings())
            if p == "/api/profiles/dns-presets":
                return self._json(netprofiles.get_dns_presets())
            if p == "/api/profiles/set-dns":
                preset = self._q(q, "preset", "dhcp")
                adapter = self._q(q, "adapter", None)
                return self._json(netprofiles.set_dns_preset(preset, adapter))
            if p == "/api/profiles/repair":
                return self._json(netprofiles.repair_network())
            if p == "/api/profiles/wol":
                mac = self._q(q, "mac", "")
                return self._json(netprofiles.send_wake_on_lan(mac))
            if p == "/api/profiles/list":
                return self._json({
                    "profiles": netprofiles.load_profiles(),
                    "active_adapter": netprofiles._get_active_interface_name()
                })
            if p == "/api/profiles/save":
                body = self._read_json_body() if self.command == "POST" else None
                if not body:
                    body = {
                        "id": self._q(q, "id", None),
                        "name": self._q(q, "name", "New Profile"),
                        "adapter": self._q(q, "adapter", ""),
                        "ip_mode": self._q(q, "ip_mode", "dhcp"),
                        "ip_address": self._q(q, "ip_address", ""),
                        "subnet_mask": self._q(q, "subnet_mask", "255.255.255.0"),
                        "gateway": self._q(q, "gateway", ""),
                        "dns_mode": self._q(q, "dns_mode", "dhcp"),
                        "primary_dns": self._q(q, "primary_dns", ""),
                        "secondary_dns": self._q(q, "secondary_dns", ""),
                        "proxy_enabled": self._q(q, "proxy_enabled", "0") == "1",
                        "proxy_server": self._q(q, "proxy_server", ""),
                        "notes": self._q(q, "notes", ""),
                        "icon": self._q(q, "icon", "📁")
                    }
                return self._json(netprofiles.upsert_profile(body))
            if p == "/api/profiles/delete":
                pid = self._q(q, "id", "")
                return self._json(netprofiles.delete_profile(pid))
            if p == "/api/profiles/apply":
                pid = self._q(q, "id", "p_home")
                return self._json(netprofiles.apply_profile(pid))
            if p == "/api/sniffer/start":
                return self._json({"active": sniffer.start_sniffer()})
            if p == "/api/sniffer/stop":
                return self._json({"active": not sniffer.stop_sniffer()})
            if p == "/api/sniffer/clear":
                return self._json({"cleared": sniffer.clear_packets()})
            if p == "/api/sniffer/status":
                return self._json(sniffer.get_sniffer_status())
            if p == "/api/sniffer/packets":
                proto = self._q(q, "proto", "ALL")
                search = self._q(q, "search", None)
                limit = int(self._q(q, "limit", "100"))
                return self._json({"packets": sniffer.get_packets(limit, proto, search)})
            if p == "/api/sniffer/follow-stream":
                src = self._q(q, "src", "")
                sport = int(self._q(q, "sport", "0"))
                dst = self._q(q, "dst", "")
                dport = int(self._q(q, "dport", "0"))
                return self._json(sniffer.follow_stream(src, sport, dst, dport))
            if p == "/api/sniffer/conversations":
                limit = int(self._q(q, "limit", "50"))
                return self._json({"conversations": sniffer.get_conversations(limit)})
            if p == "/api/interfaces/restart":
                name = self._q(q, "name", "")
                return self._json(netprofiles.restart_adapter(name))
            if p == "/api/hosts/get":
                return self._json(hostsmanager.read_hosts())
            if p == "/api/hosts/toggle-blocklist":
                enable = self._q(q, "enable", "1") == "1"
                return self._json(hostsmanager.toggle_anti_telemetry(enable))
            if p == "/api/sniffer/pcap":
                data = sniffer.export_pcap_binary()
                return self._send_bytes(data, "application/vnd.tcpdump.pcap",
                                        extra_headers={"Content-Disposition": 'attachment; filename="netvisual_capture.pcap"'})
            if p == "/api/explainer":
                return self._json(explainer.generate_network_explanation())
            if p == "/api/process/kill":
                pid_str = self._q(q, "pid", "")
                if not pid_str.isdigit() or int(pid_str) in (0, 4):
                    return self._json({"error": "Invalid or system-protected PID", "ok": False}, 400)
                code, out = run(f"taskkill /PID {pid_str} /F", 5)
                return self._json({"ok": code == 0, "output": out or "Process terminated", "pid": int(pid_str)})
            if p == "/api/server/shutdown":
                def _do_shutdown():
                    import time
                    time.sleep(0.5)
                    try:
                        if hasattr(Handler, "SHUTDOWN_CALLBACK") and callable(Handler.SHUTDOWN_CALLBACK):
                            Handler.SHUTDOWN_CALLBACK()
                    finally:
                        import os
                        os._exit(0)
                import threading
                threading.Thread(target=_do_shutdown, daemon=True).start()
                return self._json({"ok": True, "msg": "NetVisual server shutting down..."})

            if p == "/api/processes/bandwidth":
                return self._json(probes.probe_process_bandwidth())
            if p == "/api/scan/host":
                ip = self._q(q, "ip", "127.0.0.1")
                ports = self._q(q, "ports", None)
                plist = [int(x.strip()) for x in ports.split(",") if x.strip().isdigit()] if ports else None
                return self._json(portscan.portscan(ip, plist))
            if p == "/api/firewall/block":
                path = self._q(q, "path", "")
                if self.command == "POST":
                    body = self._read_json_body()
                    if body and "path" in body:
                        path = body["path"]
                return self._json(firewall.block_application(path))
            if p == "/api/firewall/unblock":
                rule = self._q(q, "rule", None)
                path = self._q(q, "path", None)
                if self.command == "POST":
                    body = self._read_json_body()
                    if body:
                        rule = body.get("rule", rule)
                        path = body.get("path", path)
                return self._json(firewall.unblock_application(rule, path))
            if p == "/api/firewall/rules":
                return self._json({"rules": firewall.list_blocked_programs()})
            if p == "/api/devices/acknowledge":
                mac = self._q(q, "mac", "")
                return self._json({"ok": history.acknowledge_device(mac)})
            if p == "/api/devices/alias":
                mac = self._q(q, "mac", "")
                alias = self._q(q, "alias", "")
                if self.command == "POST":
                    body = self._read_json_body()
                    if body:
                        mac = body.get("mac", mac)
                        alias = body.get("alias", alias)
                from ..aliases import set_alias
                set_alias(mac, alias)
                return self._json({"ok": True})
            if p == "/api/vendor/update":
                # Forces background update for all devices with unknown vendors
                topo = topology.probe()
                import threading, time
                from ..oui import _fetch_online
                def _do_update():
                    for nd in topo.get("nodes", []):
                        mac = nd.get("mac")
                        if mac and not nd.get("vendor"):
                            norm = mac.upper().replace("-", ":").replace(".", ":")
                            key = ":".join(norm.split(":")[:3])
                            _fetch_online(key)
                            time.sleep(1)
                threading.Thread(target=_do_update, daemon=True).start()
                return self._json({"ok": True, "msg": "Vendor background update triggered."})
            if p == "/api/export/devices":
                topo = topology.probe()
                devs = [n for n in topo.get("nodes", []) if n.get("kind") == "device"]
                csv_data = export.export_devices_csv(devs)
                return self._send_bytes(csv_data.encode("utf-8-sig"), "text/csv",
                                        extra_headers={"Content-Disposition": 'attachment; filename="netvisual_devices.csv"'})
            if p == "/api/export/connections":
                conns = probes.probe_connections().get("connections", [])
                csv_data = export.export_connections_csv(conns)
                return self._send_bytes(csv_data.encode("utf-8-sig"), "text/csv",
                                        extra_headers={"Content-Disposition": 'attachment; filename="netvisual_connections.csv"'})
            if p == "/api/export/packets":
                pkts = sniffer.get_packets(1000)
                csv_data = export.export_packets_csv(pkts)
                return self._send_bytes(csv_data.encode("utf-8-sig"), "text/csv",
                                        extra_headers={"Content-Disposition": 'attachment; filename="netvisual_packets.csv"'})

            # ---- history + Stage-1 analytics ---------------------------- #
            if p == "/api/history":
                r = self._range(q)
                if r is None:
                    return self._json({"error": "bad range",
                                       "hint": "use e.g. 6h, 24h, 7d, 30d, 1w"}, 400)
                pr, seconds = r
                series = history.query_range(seconds, buckets=180)
                stats = history.stats_range(seconds)
                stats["range"] = pr
                return self._json({"range": pr, "series": series, "stats": stats,
                                   "info": history.info()})
            if p == "/api/history-stats":
                r = self._range(q)
                if r is None:
                    return self._json({"error": "bad range"}, 400)
                stats = history.stats_range(r[1])
                stats["range"] = r[0]
                return self._json(stats)
            if p == "/api/history-info":
                return self._json(history.info())
            if p == "/api/status":
                r = self._range(q)
                if r is None:
                    return self._json({"error": "bad range"}, 400)
                out = history.status_range(r[1])
                out["range"] = r[0]
                return self._json(out)
            if p == "/api/devices":
                r = self._range(q)
                if r is None:
                    return self._json({"error": "bad range"}, 400)
                ev = history.device_events(r[1])
                pres = history.device_presence(r[1])
                return self._json({"range": r[0], "events": ev["events"],
                                   "event_count": ev["event_count"], "presence": pres})
            if p == "/api/baseline":
                r = self._range(q)
                if r is None:
                    return self._json({"error": "bad range"}, 400)
                metric = self._q(q, "metric", "rx_bps")
                out = history.baseline(r[1], metric)
                out["range"] = r[0]
                return self._json(out)
            if p == "/api/anomaly":
                try:
                    value = float(self._q(q, "value", None))
                except (TypeError, ValueError):
                    return self._json({"error": "value required (float)"}, 400)
                r = self._range(q)
                if r is None:
                    return self._json({"error": "bad range"}, 400)
                metric = self._q(q, "metric", "rx_bps")
                out = history.anomaly(value, r[1], metric)
                out["range"] = r[0]
                out["metric"] = metric
                return self._json(out)
            if p == "/api/alerts":
                from .. import config
                r = self._range(q)
                if r is None:
                    return self._json({"error": "bad range"}, 400)
                out = history.alerts(r[1], config.alerts())
                out["range"] = r[0]
                return self._json(out)

            self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa
            self._json({"error": str(e)}, 500)

    def _lim(self, q, name, default):
        """Clamp an integer query param to [1, 50]."""
        try:
            return max(1, min(50, int(self._q(q, name, default))))
        except (TypeError, ValueError):
            return default

    def do_POST(self):
        if urlparse(self.path).path == "/api/refresh":
            cache.clear()
            self._json({"ok": True, "msg": "cache cleared"})
            return
        return self.do_GET()
