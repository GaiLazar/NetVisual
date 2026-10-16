import concurrent.futures
from .ping import ping

SERVICES = [
    {"name": "Google", "ip": "8.8.8.8"},
    {"name": "Cloudflare", "ip": "1.1.1.1"},
    {"name": "Quad9", "ip": "9.9.9.9"},
    {"name": "AWS", "ip": "13.32.0.0"},
    {"name": "Azure", "ip": "13.107.21.200"}
]

def check_services() -> list[dict]:
    results = []
    
    def _ping_svc(svc):
        res = ping(svc["ip"], count=1)
        return {
            "name": svc["name"],
            "ip": svc["ip"],
            "reachable": res.get("reachable", False),
            "ms": res.get("avg_ms")
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_ping_svc, s): s for s in SERVICES}
        for f in concurrent.futures.as_completed(futures):
            try:
                results.append(f.result())
            except Exception:
                svc = futures[f]
                results.append({"name": svc["name"], "ip": svc["ip"], "reachable": False, "ms": None})
                
    return sorted(results, key=lambda x: x["name"])
