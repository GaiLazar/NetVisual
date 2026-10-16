"""Verify the v2 live endpoints over HTTP on port 8731. Run: python verify_v2.py"""
import urllib.request, json, time

BASE = "http://127.0.0.1:8731"
ok = fail = 0
def get(p):
    with urllib.request.urlopen(BASE + p, timeout=30) as r:
        return r.status, json.loads(r.read().decode())
def check(label, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print(f"  PASS  {label}")
    else: fail += 1; print(f"  FAIL  {label} {extra}")

# traffic (sample twice to see delta)
c, t = get('/api/traffic'); print('  traffic sample:', t['sample']); print('  history len:', len(t['history']))
time.sleep(1.2)
c, t2 = get('/api/traffic')
check("traffic /api status 200", c == 200)
check("traffic has rx_bps/tx_bps", 'rx_bps' in t2['sample'] and 'tx_bps' in t2['sample'])
check("traffic history growing", len(t2['history']) >= len(t['history']))

# activity
c, a = get('/api/activity')
check("activity /api 200", c == 200)
check("activity events list", isinstance(a['events'], list))
print('  activity sample:', a['events'][:3])

# top-talkers
c, tt = get('/api/top-talkers?n=6')
check("top-talkers 200", c == 200)
check("top-talkers non-empty", len(tt['top']) > 0)
print('  top talkers:', [(x['process'], x['established']) for x in tt['top'][:6]])

# processes
c, p = get('/api/processes')
check("processes 200", c == 200)
check("processes non-empty", len(p['processes']) > 20)

# topology vendor
c, top = get('/api/topology')
devs = [n for n in top['nodes'] if n['kind'] == 'device']
check("topology device nodes have vendor", all('vendor' in n for n in devs))
print('  device vendors:', [(d['ip'], d.get('vendor')) for d in devs[:5]])

print(f"\nRESULT: {ok} passed, {fail} failed")
import sys
sys.exit(1 if fail else 0)
