"""Verify v3 A7 'who's talking to me' (group_remote_peers). Run: python tests/test_v3_a7.py"""
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

# _remote_host edge cases
check("remote host plain", s._remote_host("1.2.3.4:443") == "1.2.3.4")
check("remote host v6", s._remote_host("[2001:db8::1]:443") == "2001:db8::1")
check("remote host dash -> None", s._remote_host("-") is None)
check("remote host 0.0.0.0:0 -> None", s._remote_host("0.0.0.0:0") is None)
check("remote host :: -> None", s._remote_host("::") is None)
check("remote host loopback -> None", s._remote_host("127.0.0.1:53") is None)

# group_remote_peers: grouping + ranking
conns = [
    {"remote": "8.8.8.8:53", "state": "ESTABLISHED", "process": "svchost.exe", "proto": "TCP"},
    {"remote": "8.8.8.8:443", "state": "ESTABLISHED", "process": "chrome.exe", "proto": "TCP"},
    {"remote": "192.168.1.1:445", "state": "ESTABLISHED", "process": "System", "proto": "TCP"},
    {"remote": "192.168.1.1:137", "state": "TIME_WAIT", "process": "System", "proto": "UDP"},
    {"remote": "0.0.0.0:0", "state": "LISTENING", "process": "python.exe", "proto": "TCP"},  # skipped
    {"remote": "[::]:0", "state": "LISTENING", "process": "node.exe", "proto": "TCP"},        # skipped
]
peers = s.group_remote_peers(conns)
check("peer count 2", len(peers) == 2, f"(n={len(peers)})")
check("8.8.8.8 first (2 est)", peers[0]["ip"] == "8.8.8.8")
check("8.8.8.8 ports", peers[0]["ports"] == [53, 443], f"({peers[0]['ports']})")
check("8.8.8.8 processes", set(peers[0]["processes"]) == {"svchost.exe", "chrome.exe"})
check("192.168.1.1 est=1", [p for p in peers if p["ip"] == "192.168.1.1"][0]["established"] == 1)
check("192.168.1.1 protos TCP/UDP", [p for p in peers if p["ip"] == "192.168.1.1"][0]["proto"] == "TCP/UDP")
check("no 0.0.0.0 peer", all(p["ip"] != "0.0.0.0" for p in peers))

# empty input
check("empty conns -> []", s.group_remote_peers([]) == [])

# live: real peers endpoint (server running separately) — just check shape here
real = s.remote_peers(limit=5)
check("remote_peers is list", isinstance(real, list))
if real:
    check("peers have local flag", all("local" in p for p in real))
    check("peers have ip", all("ip" in p for p in real))
# self-IP must be filtered out
own = None
try:
    own = s.self_netinfo().get("ip")
except Exception:
    pass
if own:
    check("own IP excluded", all(p["ip"] != own for p in s.remote_peers(50)),
          f"(own={own})")

print(f"\nRESULT: {ok} passed, {fail} failed")
import sys
sys.exit(1 if fail else 0)
