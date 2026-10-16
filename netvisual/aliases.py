import json
import threading
from .paths import DATA_DIR

_ALIASES: dict[str, str] = {}
_LOCK = threading.Lock()

def load() -> None:
    global _ALIASES
    try:
        with open(DATA_DIR / "aliases.json", "r", encoding="utf-8") as f:
            _ALIASES = json.load(f)
    except Exception:
        pass

def get_alias(mac: str) -> str:
    if not mac:
        return ""
    return _ALIASES.get(mac.upper(), "")

def set_alias(mac: str, alias: str) -> None:
    global _ALIASES
    with _LOCK:
        if alias:
            _ALIASES[mac.upper()] = alias
        else:
            _ALIASES.pop(mac.upper(), None)
        
        p = DATA_DIR / "aliases.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(_ALIASES, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

load()
