"""Conversations with the assistant, kept on this PC: one per chat, grouped by the lesson (project or file) they were about, searchable, and pinnable.
A pinned conversation is never trimmed. Everything stays in one small file in the data folder."""
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Manimo" / "data"
FILE = DATA_DIR / "chats.json"
MAX_MSGS = 60               # messages kept in one conversation
MAX_CODE = 60_000           # characters of code kept in one reply
MAX_TEXT = 30_000
KEEP_PER_LESSON = 40        # unpinned conversations kept for each lesson
MAX_BYTES = 8_000_000       # the whole file
_lock = threading.Lock()


def _load():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data
    except (OSError, ValueError):
        pass
    return {"items": []}


def _save(data):
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, FILE)
    except OSError:
        pass


def _slim(m):
    """What is worth keeping of one message: who said it, the words, the code, what kind of step it was and what it cost."""
    if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
        return None
    out = {"role": m["role"], "text": str(m.get("text") or "")[:MAX_TEXT]}
    if m.get("code"):
        out["code"] = str(m["code"])[:MAX_CODE]
    if m.get("kind"):
        out["kind"] = str(m["kind"])[:12]
    if isinstance(m.get("usage"), dict):
        out["usage"] = {k: m["usage"].get(k) for k in ("in", "out", "rounds", "seconds", "exact") if isinstance(m["usage"].get(k), (int, float, bool))}
    if m.get("error"):
        out["error"] = str(m["error"])[:400]
    return out


def _title(msgs):
    for m in msgs:
        if m["role"] == "user" and m["text"].strip():
            t = " ".join(m["text"].split())
            t = re.sub(r"^(Lesson plan \(approved\):|The plan above is approved\.|The solution above is correct\.)\s*", "", t)
            return t[:70] + ("…" if len(t) > 70 else "")
    return "New conversation"


def _trim(data):
    """Keep each lesson's newest unpinned conversations, and the whole file under its size limit. Pinned conversations stay."""
    by = {}
    for it in sorted(data["items"], key=lambda i: -i["updated"]):
        if not it.get("pinned"):
            by.setdefault(it["key"], []).append(it)
    drop = {id(i) for lst in by.values() for i in lst[KEEP_PER_LESSON:]}
    data["items"] = [i for i in data["items"] if id(i) not in drop]
    while len(json.dumps(data, ensure_ascii=False)) > MAX_BYTES:
        old = [i for i in data["items"] if not i.get("pinned")]
        if not old:
            break
        data["items"].remove(min(old, key=lambda i: i["updated"]))


def save(body):
    """Create or update a conversation. An empty conversation is not kept."""
    msgs = [m for m in (_slim(x) for x in (body.get("msgs") or [])[-MAX_MSGS:]) if m]
    while msgs and msgs[0]["role"] != "user":              # a long chat is cut from the front: it still starts with a question
        msgs.pop(0)
    key = " ".join(str(body.get("key") or "Untitled").split())[:120]
    cid = str(body.get("id") or "")
    if not any(m["role"] == "user" for m in msgs):
        return {"id": cid or None}, 200
    with _lock:
        data = _load()
        it = next((i for i in data["items"] if i["id"] == cid), None)
        if it is None:
            it = {"id": secrets.token_hex(5), "key": key, "created": int(time.time()), "pinned": False}
            data["items"].append(it)
        it.update(key=key, updated=int(time.time()), title=_title(msgs), msgs=msgs)
        _trim(data)
        _save(data)
        return {"id": it["id"]}, 200


def _snippet(it, q):
    for m in it["msgs"]:
        t = " ".join(m["text"].split())
        i = t.lower().find(q)
        if i >= 0:
            lo = max(0, i - 30)
            return ("…" if lo else "") + t[lo:i + len(q) + 50] + ("…" if i + len(q) + 50 < len(t) else "")
    return ""


def listing(body):
    """Pinned first, then newest. `key` limits it to one lesson; `q` searches titles and every message."""
    key, q = body.get("key"), " ".join(str(body.get("q") or "").lower().split())
    with _lock:
        data = _load()
    out = []
    for it in data["items"]:
        if key and it["key"] != key:
            continue
        hit = bool(q) and (q in it["title"].lower() or any(q in m["text"].lower() for m in it["msgs"]))
        if q and not hit:
            continue
        out.append({"id": it["id"], "key": it["key"], "title": it["title"], "updated": it["updated"], "pinned": bool(it.get("pinned")), "n": len(it["msgs"]),
                    "snippet": _snippet(it, q) if q and q not in it["title"].lower() else ""})
    out.sort(key=lambda i: (not i["pinned"], -i["updated"]))
    return {"items": out}, 200


def get(body):
    with _lock:
        it = next((i for i in _load()["items"] if i["id"] == str(body.get("id") or "")), None)
    if it is None:
        return {"error": "That conversation is no longer kept."}, 404
    return {"id": it["id"], "key": it["key"], "title": it["title"], "msgs": it["msgs"]}, 200


def pin(body):
    with _lock:
        data = _load()
        it = next((i for i in data["items"] if i["id"] == str(body.get("id") or "")), None)
        if it is None:
            return {"error": "That conversation is no longer kept."}, 404
        it["pinned"] = bool(body.get("pinned"))
        _save(data)
    return {"ok": True, "pinned": it["pinned"]}, 200


def delete(body):
    with _lock:
        data = _load()
        data["items"] = [i for i in data["items"] if i["id"] != str(body.get("id") or "")]
        _save(data)
    return {"ok": True}, 200
