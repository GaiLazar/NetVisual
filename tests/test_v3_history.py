"""Verify v3 History + Trends (persistent store, API, UI logic).

Run:  python test_v3_history.py
  - Uses a throwaway DB (NETVISUAL_HISTORY_DB in temp) so it never touches real data.
  - Seeds samples, starts a fresh server on port 8732, exercises the new API
    endpoints over live HTTP, and checks the JS trend functions in Node.
Exit 0 on all-pass.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8732
BASE = f"http://127.0.0.1:{PORT}"

# isolated DB for this test run
_tmpdir = tempfile.mkdtemp(prefix="nvh-")
DB = os.path.join(_tmpdir, "test_history.db")
os.environ["NETVISUAL_HISTORY_DB"] = DB
os.environ["NETVISUAL_HISTORY_INTERVAL"] = "0"  # sampler OFF during the test (deterministic rows)

sys.path.insert(0, HERE)
from netvisual import history as h  # noqa: E402

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

# ---- backend module: seeding + persistence + pruning -----------------------
h.init()
h.clear()
now = int(time.time())
# 40 samples over ~20 min, with a known bandwidth envelope
for i in range(40):
    h.record({
        "ts": now - 1200 + i * 30,
        "rx_bps": 1000 + i * 100, "tx_bps": 500 + i * 50,
        "recv_total": i * 1000, "sent_total": i * 500,
        "devices": 3 + (i % 4), "connections": 20 + i, "tcp_est": 10 + (i % 5),
        "lat_ms": (None if i % 10 == 0 else 15 + i),  # some dropped pings
        "gw_up": (i % 10 != 0),
    })
info = h.info()
check("H backend: 40 rows seeded", info["rows"] == 40, f"(rows={info['rows']})")
check("H backend: retention reported", info["retention_days"] == 30, f"(info={info})")
# pruning: drop anything older than 10 min
pruned = h.prune(days=0)  # days=0 -> cutoff = now -> deletes everything
check("H backend: prune removes old rows", pruned == 40, f"(pruned={pruned})")
h.clear(); h.init()
# re-seed a small deterministic set for the endpoint checks
h.record({"ts": now - 100, "rx_bps": 100, "tx_bps": 200, "recv_total": 10, "sent_total": 20,
          "devices": 5, "connections": 10, "tcp_est": 6, "lat_ms": 20, "gw_up": True})
h.record({"ts": now - 50, "rx_bps": 300, "tx_bps": 400, "recv_total": 60, "sent_total": 120,
          "devices": 7, "connections": 14, "tcp_est": 9, "lat_ms": 30, "gw_up": True})
h.record({"ts": now - 10, "rx_bps": 500, "tx_bps": 600, "recv_total": 120, "sent_total": 240,
          "devices": 6, "connections": 18, "tcp_est": 12, "lat_ms": 40, "gw_up": False})
q = h.query_range(86400, buckets=100)
check("H backend: query returns 3 pts", len(q) == 3, f"(n={len(q)})")
check("H backend: stats peak correct", h.stats_range(86400)["rx_peak"] == 500,
      f"(peak={h.stats_range(86400)['rx_peak']})")
check("H backend: data_rx uses cumulative delta", h.stats_range(86400)["data_rx_bytes"] == 120 - 10,
      f"(data_rx={h.stats_range(86400)['data_rx_bytes']})")

# ---- live HTTP: start server, hit the new endpoints -----------------------
env = dict(os.environ, NETVISUAL_PORT=str(PORT))
proc = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
def stop():
    try: proc.terminate()
    except Exception: pass
    try: proc.wait(timeout=5)
    except Exception: proc.kill()
import atexit; atexit.register(stop)
# wait for readiness
ready = False
for _ in range(80):
    hi = get("/api/history-info", 1)
    if "rows" in hi:
        ready = True
        break
    time.sleep(0.5)
check("H server: ready", ready, "(server did not respond to /api/history-info)")

hi = get("/api/history-info")
check("H api: /api/history-info shape",
      all(k in hi for k in ("rows", "first_ts", "last_ts", "retention_days", "interval_s", "sampling")),
      f"(keys={list(hi.keys())} err={hi.get('__error__')})")

d24 = get("/api/history?range=24h")
check("H api: /api/history 24h shape",
      all(k in d24 for k in ("range", "series", "stats", "info")),
      f"(keys={list(d24.keys())} err={d24.get('__error__')})")
check("H api: series non-empty", len(d24.get("series", [])) == 3, f"(n={len(d24.get('series', []))})")
st = d24.get("stats", {})
check("H api: stats fields",
      all(k in st for k in ("data_rx_bytes", "data_tx_bytes", "rx_peak", "tx_peak", "lat_avg",
                            "devices_peak", "gw_up_pct", "points")),
      f"(stats={st})")
check("H api: rx_peak == 500", st.get("rx_peak") == 500, f"(peak={st.get('rx_peak')})")
check("H api: gw_up_pct correct (2/3 up)", abs(st.get("gw_up_pct", -1) - 66.7) < 0.2,
      f"(gw_up_pct={st.get('gw_up_pct')})")

# range validation: server rejects bad range with HTTP 400
bad = get("/api/history?range=bogus")
check("H api: bad range rejected (400)",
      "error" in bad or "400" in str(bad.get("__error__", "")),
      f"(resp={bad})")
# 7d works (even with no data)
d7 = get("/api/history?range=7d")
check("H api: 7d returns structure", "series" in d7 and "stats" in d7, f"(keys={list(d7.keys())})")

stop()

# ---- frontend: JS trend helpers in Node ------------------------------------
js_src = open(os.path.join(HERE, "static", "app.js"), encoding="utf-8").read()
def extract(name):
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

fn = extract("drawTrChart")
node_prog = f'''
// minimal SVG shim so drawTrChart can run without a DOM
const mk = (tag) => ({{ tag, innerHTML: "" }});
globalThis.document = {{}};
const svg = mk("svg");
// drawTrChart references $(...) only for the element passed in; we pass svg directly
{fn.replace("if (!svg) return;", "if (!svg) return;")}
const pts = [10, 20, null, 40, 50];
drawTrChart(svg, pts, {{color:"#34d399"}});
const out = {{}};
out.has_line = svg.innerHTML.includes("M") && svg.innerHTML.includes("L");
out.has_gap_restart = (svg.innerHTML.match(/M/g) || []).length >= 2; // null restarts path with M
out.no_nan = !svg.innerHTML.includes("NaN") && !svg.innerHTML.includes("undefined");
// empty case
const svg2 = mk("svg");
drawTrChart(svg2, [], {{}});
out.empty_msg = svg2.innerHTML.includes("no data in this window");
console.log(JSON.stringify(out));
'''
r = subprocess.run(["node", "-e", node_prog], capture_output=True, text=True, cwd=HERE, timeout=60)
if r.returncode != 0:
    check("H ui: node ran", False, f"stderr={r.stderr.strip()[:400]}")
    print(f"\nRESULT: {ok} passed, {fail} failed")
    sys.exit(1)
o = json.loads(r.stdout.strip().splitlines()[-1])
check("H ui: chart draws a line", o["has_line"] is True, f"(has_line={o['has_line']})")
check("H ui: null gaps restart path (M count>=2)", o["has_gap_restart"] is True, f"(gap={o['has_gap_restart']})")
check("H ui: no NaN/undefined in SVG", o["no_nan"] is True, f"(no_nan={o['no_nan']})")
check("H ui: empty window shows placeholder", o["empty_msg"] is True, f"(empty={o['empty_msg']})")

# DOM sanity: the tab + panel + range buttons + chart svgs exist in index.html
html = open(os.path.join(HERE, "static", "index.html"), encoding="utf-8").read()
check("H dom: trends tab present", 'data-tab="trends"' in html)
check("H dom: trends panel present", 'id="panel-trends"' in html)
check("H dom: range buttons present",
      all(f'data-range="{x}"' in html for x in ("6h", "24h", "7d", "30d")))
check("H dom: 4 chart svgs present",
      all(f'id="tr{c}Chart"' in html for c in ("Bw", "Lat", "Dev", "Conn")))

print(f"\nRESULT: {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
