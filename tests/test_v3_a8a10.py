"""Verify v3 A8 (portscan) + A9 (PTR) + A10 (gateway latency). Run: python test_v3_a8a10.py
Also verifies the three new HTTP endpoints against a live server on 127.0.0.1:8730."""
import socket
import threading
import time
import urllib.request
import os as _os, sys as _sys
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path: _sys.path.insert(0, _ROOT)

import server as s

ok = fail = 0
def check(label, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print(f"  PASS  {label}")
    else:
        fail += 1; print(f"  FAIL  {label} {extra}")

# ---- A8: portscan against a local listener -------------------------------
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 0))
open_port = srv.getsockname()[1]
srv.listen(4)
def accept_once():
    try:
        c, _ = srv.accept()
        c.close()
    except Exception:
        pass
threading.Thread(target=accept_once, daemon=True).start()
time.sleep(0.2)

scan = s.portscan("127.0.0.1", ports=[open_port, 1], timeout=0.8)
check("scan total == 2", scan["total"] == 2, f"(total={scan.get('total')})")
check("open port detected", open_port in scan["open_ports"], f"(open={scan['open_ports']})")
check("port 1 closed", any(p["port"] == 1 and not p["open"] for p in scan["ports"]))
check("ports sorted", [p["port"] for p in scan["ports"]] == sorted(p["port"] for p in scan["ports"]))
check("open_count correct", scan["open_count"] == 1, f"(n={scan['open_count']})")

bad = s.portscan("not-an-ip")
check("bad IP -> error", bad.get("error") == "invalid IP", f"({bad})")
bad2 = s.portscan("127.0.0.1", ports=["99999", "abc", "80"])
check("port clamped / bad dropped", any(p["port"] == 80 for p in bad2["ports"]) and
      all(1 <= p["port"] <= 65535 for p in bad2["ports"]), f"(ports={[p['port'] for p in bad2['ports']]})")
try:
    srv.close()
except Exception:
    pass

# ---- A9: reverse DNS ------------------------------------------------------
r = s.reverse_dns("127.0.0.1")
check("PTR localhost", r["found"] is True and bool(r["name"]), f"({r})")
r2 = s.reverse_dns("bad..ip")
check("PTR bad IP -> not found", r2["found"] is False, f"({r2})")

# ---- A10: latency sampler -------------------------------------------------
lat = s.sample_latency()
check("latency has sample", "sample" in lat and "history" in lat)
check("latency sample shape", all(k in lat["sample"] for k in ("ts", "ms", "reachable", "host")))
lat2 = s.sample_latency()
check("latency ring grows", len(lat2["history"]) >= 2, f"(n={len(lat2['history'])})")

# ---- HTTP endpoints (live server) ----------------------------------------
def get(path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8730{path}", timeout=15) as resp:
            import json
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"__error__": str(e)}

ps = get("/api/portscan?ip=127.0.0.1&ports=80")
check("HTTP portscan shape", "ports" in ps and "open_count" in ps, f"({ps.get('__error__', ps.get('error'))})")
ptr = get("/api/ptr?ip=127.0.0.1")
check("HTTP PTR shape", "found" in ptr and "name" in ptr, f"({ptr.get('__error__', ptr.get('error'))})")
lat_h = get("/api/latency")
check("HTTP latency shape", "sample" in lat_h and "history" in lat_h, f"({lat_h.get('__error__', lat_h.get('error'))})")

print(f"\nRESULT: {ok} passed, {fail} failed")
import sys
sys.exit(1 if fail else 0)
