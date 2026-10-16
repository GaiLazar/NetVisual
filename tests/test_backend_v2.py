"""Verify v2 backend additions. Run: python tests/test_backend_v2.py"""
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

# OUI vendor
check("OUI Apple", s.lookup_vendor("9C-9D-7E-49-31-1D") == "Apple")
check("OUI unknown -> ''", s.lookup_vendor("AA-BB-CC-DD-EE-FF") == "")

# process names parse
pn = s.process_names()
check("process_names non-empty", len(pn) > 20, f"(n={len(pn)})")

# tasklist csv parser
sample = '"System","4","Services","0","1 K"\n"svchost.exe","1234","Services","0","2 K"\n'
m = s.parse_tasklist_csv(sample)
check("tasklist pid 1234", m.get(1234) == "svchost.exe")
check("tasklist pid 4", m.get(4) == "System")

# netstat -e parser
ne = s.parse_netstat_e("Bytes                    1890942988       676826330\nUnicast packets             3042150         2729130\n")
check("netstat-e recv_bytes", ne["recv_bytes"] == 1890942988)
check("netstat-e sent_pkts", ne["sent_pkts"] == 2729130)

# activity feed records device changes
s._record_devices(["192.168.1.100"])
s._record_devices(["192.168.1.200"])
ev = s.activity_feed()
check("activity has device_up", any(e["kind"] == "device_up" for e in ev))
check("activity has device_down", any(e["kind"] == "device_down" for e in ev))

# listening-port recorder
s._record_listening([80, 443])
s._record_listening([80, 8080])
ev2 = s.activity_feed()
check("activity has port_open (8080)", any(e["msg"].find("8080") != -1 for e in ev2))

# topology now carries vendor
t = s.build_topology()
devs = [n for n in t["nodes"] if n.get("kind") == "device"]
check("device nodes have vendor key", all("vendor" in n for n in devs))

print(f"\nRESULT: {ok} passed, {fail} failed")
import sys
sys.exit(1 if fail else 0)
