"""Verify v3 A11 (deep-scan progress) + A12 (bw peak/avg) + A13 (filter) + A14 (CSV).

Run:  python test_v3_a11a14.py
  - A11/A12: backend + live HTTP against a freshly-started server (port 8731).
    The test launches its own dedicated server child process, so it is
    self-contained — no dependency on what is running on 8730.
  - A13/A14: pure JS functions exercised in Node (no DOM needed).
Exit 0 on all-pass.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path: sys.path.insert(0, HERE)
PORT = 8731
BASE = f"http://127.0.0.1:{PORT}"

ok = fail = 0
def check(label, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print(f"  PASS  {label}")
    else:
        fail += 1; print(f"  FAIL  {label} {extra}")

def get(path, timeout=20):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"__error__": str(e)}

# ---- dedicated test server (port 8731) ------------------------------------
_srv_proc = None

def start_test_server():
    global _srv_proc
    env = dict(os.environ)
    env["NETVISUAL_PORT"] = str(PORT)
    env.pop("NETVISUAL_TRAY", None)  # never spawn a tray icon in tests
    _srv_proc = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "netvisual_app.py")],
        env=env, cwd=HERE,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):  # up to ~25s for boot
        if _srv_proc.poll() is not None:
            raise RuntimeError(f"test server exited early (rc={_srv_proc.returncode})")
        time.sleep(0.25)
        try:
            with urllib.request.urlopen(BASE + "/api/summary", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            continue
    _srv_proc.kill()
    raise RuntimeError("test server did not become ready on port " + str(PORT))

def stop_test_server():
    global _srv_proc
    if _srv_proc is None:
        return
    try:
        _srv_proc.kill()
        _srv_proc.wait(timeout=10)
    except Exception:
        pass
    _srv_proc = None

start_test_server()
try:
    # ---- A12 backend: /api/traffic stats ------------------------------------
    t = get("/api/traffic")
    check("A12 traffic has stats", "stats" in t, f"({t.get('__error__') or list(t.keys())})")
    st = t.get("stats", {})
    check("A12 stats fields", all(k in st for k in ("rx_peak", "tx_peak", "rx_avg", "tx_avg", "samples")),
          f"(stats={st})")
    # stats consistent with history
    hist = t.get("history", [])
    rx = [p.get("rx_bps", 0) for p in hist]
    check("A12 rx_peak == max(history.rx)", hist and st.get("rx_peak") == max(rx),
          f"(peak={st.get('rx_peak')} max={max(rx) if rx else None})")
    check("A12 rx_avg sane", not hist or st.get("rx_avg") == round(sum(rx) / len(rx)), f"(avg={st.get('rx_avg')})")
    check("A12 samples == len(hist)", st.get("samples") == len(hist), f"(samples={st.get('samples')} n={len(hist)})")

    # ---- A11 backend: sweep_status shape + probe_topology sweep path --------
    import server as s
    ss = s.sweep_status()
    check("A11 sweep_status shape",
          all(k in ss for k in ("running", "total", "done", "found", "percent", "found_ips")),
          f"(keys={list(ss.keys())})")
    check("A11 percent in [0,100]", 0 <= ss["percent"] <= 100, f"(pct={ss['percent']})")

    # The sweep path must run FRESH (bypass cache) so progress is live. Call it on loopback.
    topo = s.probe_topology(sweep=True)
    check("A11 sweep returns nodes", "nodes" in topo and len(topo["nodes"]) >= 1, f"(nodes={len(topo.get('nodes', []))})")
    ss2 = s.sweep_status()
    check("A11 sweep recorded progress", ss2["total"] > 0 and ss2["done"] == ss2["total"],
          f"(total={ss2['total']} done={ss2['done']})")
    check("A11 sweep found >= 1 (loopback/hosts)", ss2["found"] >= 1, f"(found={ss2['found']})")

    # /api/scan-status endpoint live
    h = get("/api/scan-status")
    check("A11 /api/scan-status live", "percent" in h and "running" in h, f"({h.get('__error__') or list(h.keys())})")
finally:
    stop_test_server()

# ---- A13/A14: JS pure functions in Node -----------------------------------
# Extract just the two dependency-free functions from app.js and eval in Node.
js_src = open(os.path.join(HERE, "static", "app.js"), encoding="utf-8").read()

def extract(name):
    # grab "function NAME(...) { ... }" with brace matching
    key = f"function {name}("
    i = js_src.index(key)
    j = js_src.index("{", i)
    depth = 0
    for k in range(j, len(js_src)):
        c = js_src[k]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return js_src[i:k + 1]
    raise ValueError(f"could not extract {name}")

fn_filter = extract("filterDevices")
fn_csv = extract("devicesToCsv")

node_prog = f'''
{fn_filter}
{fn_csv}
const sample = [
  {{ip:"192.168.1.1", kind:"gateway", mac:"AA:BB:CC:DD:EE:FF", vendor:"Cisco", reach:true, ms:1, type:"dynamic"}},
  {{ip:"192.168.1.50", kind:"device", mac:"11:22:33:44:55:66", vendor:"Apple", reach:true, ms:5, type:"dynamic"}},
  {{ip:"192.168.1.99", kind:"device", mac:"DE:AD:BE:EF:00:01", vendor:"Unknown, Inc", reach:false, ms:null, type:"static"}},
  {{ip:"192.168.1.200", kind:"device", mac:"99:88:77:66:55:44", vendor:"", reach:true, ms:12, type:"dynamic"}},
];
const out = {{}};
out.all = filterDevices(sample, {{}}).length;
out.q_ip = filterDevices(sample, {{q:"192.168.1.50"}}).length;
out.q_vendor_ci = filterDevices(sample, {{q:"apple"}}).length;
out.status_up = filterDevices(sample, {{status:"up"}}).length;
out.status_down = filterDevices(sample, {{status:"down"}}).length;
out.vendor_apple = filterDevices(sample, {{vendor:"Apple"}}).length;
out.vendor_unknown = filterDevices(sample, {{vendor:"unknown"}}).length;
out.combo = filterDevices(sample, {{q:"192", status:"up", vendor:"Apple"}}).length;
const csv = devicesToCsv(sample);
out.csv_head = csv.charCodeAt(0) === 0xFEFF && csv.split("\\r\\n")[0] === "\\uFEFF" + "IP,Kind,MAC,Vendor,Status,Latency_ms,ARP_type";
out.csv_rows = csv.split("\\r\\n").filter(l=>l.length).length - 1;
// RFC4180: the vendor with a comma must be quoted
out.csv_quote = csv.split("\\r\\n").some(l => l.includes('"Unknown, Inc"'));
console.log(JSON.stringify(out));
'''
r = subprocess.run(["node", "-e", node_prog], capture_output=True, text=True, cwd=HERE, timeout=60)
if r.returncode != 0:
    check("A13/A14 node ran", False, f"stderr={r.stderr.strip()[:400]}")
    print(f"\nRESULT: {ok} passed, {fail} failed")
    sys.exit(1)
o = json.loads(r.stdout.strip().splitlines()[-1])
check("A13 filter: all = 4", o["all"] == 4, f"(all={o['all']})")
check("A13 filter: q by ip = 1", o["q_ip"] == 1, f"(q_ip={o['q_ip']})")
check("A13 filter: q vendor case-insens = 1", o["q_vendor_ci"] == 1, f"(ci={o['q_vendor_ci']})")
check("A13 filter: status up = 3", o["status_up"] == 3, f"(up={o['status_up']})")
check("A13 filter: status down = 1", o["status_down"] == 1, f"(down={o['status_down']})")
check("A13 filter: vendor exact = 1", o["vendor_apple"] == 1, f"(apple={o['vendor_apple']})")
check("A13 filter: vendor unknown = 1 (blank)", o["vendor_unknown"] == 1, f"(unknown={o['vendor_unknown']})")
check("A13 filter: combo = 1", o["combo"] == 1, f"(combo={o['combo']})")
check("A14 csv: BOM + header", o["csv_head"] is True, f"(csv_head={o['csv_head']})")
check("A14 csv: 4 data rows", o["csv_rows"] == 4, f"(rows={o['csv_rows']})")
check("A14 csv: comma vendor quoted (RFC4180)", o["csv_quote"] is True, f"(quote={o['csv_quote']})")

print(f"\nRESULT: {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
