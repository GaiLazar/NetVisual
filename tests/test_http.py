"""HTTP endpoint self-test. Run: python test_http.py (server must be running)."""
import json
import urllib.request
import urllib.parse

BASE = "http://127.0.0.1:8730"
ok = 0
fail = 0

def check(label, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {label} {extra}")
    else:
        fail += 1
        print(f"  FAIL  {label} {extra}")

def get(path, expect_code=200):
    try:
        with urllib.request.urlopen(BASE + path, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}

print("== /api/topology ==")
c, t = get("/api/topology")
check("status 200", c == 200)
devs = [n["ip"] for n in t.get("nodes", []) if n.get("kind") == "device"]
check("has self node", any(n.get("kind") == "this-pc" for n in t.get("nodes", [])))
check("has gateway node", any(n.get("kind") == "gateway" for n in t.get("nodes", [])))
check("has devices", len(devs) >= 3, f"(n={len(devs)})")
check("edges present", len(t.get("edges", [])) >= len(devs))

print("== /api/interfaces ==")
c, d = get("/api/interfaces")
check("status 200", c == 200)
check("has interfaces", len(d.get("interfaces", [])) >= 1)

print("== /api/routes ==")
c, d = get("/api/routes")
check("status 200", c == 200)
check("has routes", len(d.get("routes", [])) >= 1)

print("== /api/connections ==")
c, d = get("/api/connections")
check("status 200", c == 200)
check("has connections", len(d.get("connections", [])) >= 1)

print("== /api/ping (localhost) ==")
c, d = get("/api/ping?ip=127.0.0.1")
check("status 200", c == 200)
check("reachable field", "reachable" in d)

print("== /api/raw allowlist ==")
c, d = get("/api/commands")
check("status 200", c == 200)
check("has allowed list", len(d.get("allowed", [])) >= 3, f"(n={len(d.get('allowed', []))})")

print("== /api/raw: disallowed command must be 400 ==")
bad = "notallowed" + chr(32) + "xyz"
c, d = get("/api/raw?cmd=" + urllib.parse.quote(bad, safe=""))
check("rejected with 400", c == 400, f"(status={c})")
check("returns error", "error" in d)

print("== /api/raw: allowed command returns output ==")
allowed = d.get("allowed", [])
# pick a safe allowed cmd that is definitely present
safe_cmd = next((a for a in allowed if a.startswith("route")), None)
if safe_cmd:
    c, d = get("/api/raw?cmd=" + urllib.parse.quote(safe_cmd, safe=""))
    check("allowed cmd status 200", c == 200, f"({safe_cmd!r})")
    check("allowed cmd has output", "output" in d and len(d["output"]) > 0)

print("== /api/summary ==")
c, s = get("/api/summary")
check("status 200", c == 200)
check("self_ip present", bool(s.get("self_ip")))
check("neighbors >= 1", s.get("neighbors", 0) >= 1, f"(n={s.get('neighbors')})")

print("== static files ==")
for p in ["/", "/static/app.js", "/static/style.css"]:
    try:
        with urllib.request.urlopen(BASE + p, timeout=15) as r:
            body = r.read()
            check(f"GET {p}", r.status == 200 and len(body) > 100, f"({len(body)}b)")
    except Exception as e:
        check(f"GET {p}", False, str(e))

print(f"\nRESULT: {ok} passed, {fail} failed")
import sys
sys.exit(1 if fail else 0)
