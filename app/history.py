"""Version history for the editor: a snapshot when the user pauses typing and before every render, so no edit is ever lost.
Stored on this PC only, one small file per code file (keyed by its name), the newest 30 kept."""
import difflib
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Manimo" / "data" / "history"
KEEP = 30
MAX_CODE = 400_000
_lock = threading.Lock()


def _file(key):
    return DATA_DIR / (hashlib.sha1(str(key or "untitled").lower().encode("utf-8")).hexdigest()[:16] + ".json")


def _load(key):
    try:
        data = json.loads(_file(key).read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [s for s in data if isinstance(s, dict) and isinstance(s.get("code"), str)]
    except (OSError, ValueError):
        pass
    return []


def _save(key, items):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        f = _file(key)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, f)
    except OSError:
        pass


def change_summary(old, new):
    """'+3 -1' style counts of added and removed lines."""
    added = removed = 0
    for ln in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0):
        if ln.startswith("+") and not ln.startswith("+++"):
            added += 1
        elif ln.startswith("-") and not ln.startswith("---"):
            removed += 1
    return added, removed


def save(body):
    """Keep a snapshot unless it is empty or the same as the newest one."""
    key, code = body.get("key"), str(body.get("code") or "")[:MAX_CODE]
    if not code.strip():
        return {"saved": False}, 200
    with _lock:
        items = _load(key)
        if items and items[-1]["code"] == code:
            return {"saved": False}, 200
        items.append({"id": secrets.token_hex(4), "ts": int(time.time()), "reason": str(body.get("reason") or "Edited")[:40], "code": code})
        _save(key, items[-KEEP:])
    return {"saved": True}, 200


def listing(body):
    """Newest first, without the code: when, why, how long, and what changed since the snapshot before it."""
    with _lock:
        items = _load(body.get("key"))
    out = []
    for i, s in enumerate(items):
        added, removed = change_summary(items[i - 1]["code"], s["code"]) if i else (len(s["code"].splitlines()), 0)
        out.append({"id": s["id"], "ts": s["ts"], "reason": s.get("reason", ""), "lines": len(s["code"].splitlines()), "added": added, "removed": removed})
    return {"items": out[::-1]}, 200


def get(body):
    """One snapshot's code, and how it differs from the code in the editor now (- only in the snapshot, + only in the editor)."""
    with _lock:
        items = _load(body.get("key"))
    snap = next((s for s in items if s["id"] == body.get("id")), None)
    if snap is None:
        return {"error": "That version is no longer kept."}, 404
    now = str(body.get("code") or "")[:MAX_CODE]
    diff = [ln for ln in difflib.unified_diff(snap["code"].splitlines(), now.splitlines(), lineterm="", n=2) if not ln.startswith(("+++", "---"))]
    return {"code": snap["code"], "diff": diff[:600], "same": snap["code"] == now}, 200
