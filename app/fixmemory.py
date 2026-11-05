"""Fix memory: when the assistant fixes a problem in a scene, Manimo remembers the problem and the change that fixed it, on this PC only.
The next time a similar problem comes up, the closest few are added to the request, so the assistant does not have to rediscover them.
Nothing is sent anywhere by this module; the saved text goes to the AI service only inside a later fix request, like the rest of the request."""
import difflib
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Manimo" / "data"
FILE = DATA_DIR / "fixes.json"
MAX_ITEMS = 200
MAX_CHANGED = 40            # a fix that rewrote more lines than this was a rewrite, not something to reuse
MIN_SCORE = 0.34            # how alike two problems must be
_lock = threading.Lock()
_STOP = {"the", "and", "for", "with", "this", "that", "line", "not", "are", "was", "has", "have", "from", "but", "your", "can", "its", "got",
         "error", "scene", "code", "problem", "found", "file", "object", "name", "none"}


def _load():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            data["items"] = [it for it in data["items"] if isinstance(it, dict) and it.get("problem") and it.get("fix")]
            for it in data["items"]:
                it.setdefault("id", secrets.token_hex(4))
            return data
    except (OSError, ValueError):
        pass
    return {"enabled": True, "items": []}


def _save(data):
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, FILE)
    except OSError:
        pass


def tokens(text):
    """The words that describe a problem: identifiers and error names, without numbers, paths or line numbers."""
    text = re.sub(r"[A-Za-z]:\\[^\s]*|/[\w./-]+", " ", str(text or ""))
    text = re.sub(r"\d+(\.\d+)?", " ", text)
    return {w for w in re.findall(r"[a-z_][a-z0-9_]{2,}", text.lower()) if w not in _STOP}


def similarity(a, b):
    ta, tb = tokens(a), tokens(b)
    return 2 * len(ta & tb) / (len(ta) + len(tb)) if ta and tb else 0.0      # Dice: a short error still matches a longer saved one


def diff_of(old, new, limit_lines=14, limit_chars=700):
    """The changed lines only (- removed, + added), short enough to put in a request. ("", n) when nothing changed."""
    lines = [ln for ln in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0) if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
    changed = len(lines)
    text = "\n".join(l[:160] for l in lines[:limit_lines])
    return (text[:limit_chars], changed)


def gist(error_text):
    """The part of a traceback that names the problem: its last two non-empty lines."""
    lines = [ln.strip() for ln in str(error_text or "").splitlines() if ln.strip()]
    return " ".join(lines[-2:])[:300]


def enabled():
    with _lock:
        return bool(_load().get("enabled", True))


def stats():
    with _lock:
        d = _load()
    return {"enabled": bool(d.get("enabled", True)), "count": len(d["items"])}


def set_enabled(on):
    with _lock:
        d = _load()
        d["enabled"] = bool(on)
        _save(d)
    return stats()


def forget():
    with _lock:
        d = _load()
        d["items"] = []
        _save(d)
    return stats()


def record(engine, problems, old_code, new_code):
    """Save one fix: `problems` are the texts the check reported for old_code, new_code is the version that came back clean."""
    problems = [str(p).strip() for p in problems if str(p).strip()]
    if not problems:
        return False
    change, changed = diff_of(old_code, new_code)
    if not change or changed > MAX_CHANGED:
        return False
    problem = " | ".join(p[:220] for p in problems[:3])
    with _lock:
        d = _load()
        if not d.get("enabled", True):
            return False
        for it in d["items"]:
            if it.get("engine") == engine and similarity(it["problem"], problem) >= 0.8:      # the same problem again: keep one, refreshed
                it.update(fix=change, ts=int(time.time()), uses=it.get("uses", 0) + 1)
                _save(d)
                return True
        d["items"].append({"id": secrets.token_hex(4), "engine": engine, "problem": problem, "fix": change, "ts": int(time.time()), "uses": 0, "last_used": 0})
        d["items"] = d["items"][-MAX_ITEMS:]
        _save(d)
    return True


def find(engine, text, limit=3):
    """The saved fixes closest to `text`, best first. Empty when switched off or nothing is close enough."""
    with _lock:
        d = _load()
    if not d.get("enabled", True) or not d["items"]:
        return []
    scored = [(similarity(it["problem"], text), it) for it in d["items"] if it.get("engine") == engine]
    scored = [s for s in scored if s[0] >= MIN_SCORE]
    scored.sort(key=lambda s: (-(s[0] + 0.02 * min(s[1].get("uses", 0), 5)), -s[1].get("ts", 0)))      # a fix that was reused before ranks a little higher
    return [it for _, it in scored[:limit]]


def used(items):
    """Note that these saved fixes were put in a request (shown as 'used n times' in the list)."""
    ids = {it.get("id") for it in items}
    if not ids:
        return
    with _lock:
        d = _load()
        for it in d["items"]:
            if it["id"] in ids:
                it["uses"] = it.get("uses", 0) + 1
                it["last_used"] = int(time.time())
        _save(d)


def listing():
    """Everything saved, newest first, for the settings list."""
    with _lock:
        d = _load()
    return [{k: it.get(k) for k in ("id", "engine", "problem", "fix", "uses", "ts", "last_used")} for it in reversed(d["items"])]


def delete(item_id):
    with _lock:
        d = _load()
        d["items"] = [it for it in d["items"] if it["id"] != item_id]
        _save(d)
    return stats()


# ---------------------------------------------------------------- sharing a pack of fixes as text
def _clean_text(text, limit):
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", str(text or ""))
    return text.replace("<", "‹").replace(">", "›")[:limit].strip()          # no tags: shared text must not be able to close the block it sits in


def export_pack():
    items = listing()
    return {"manimo_fixes": 1, "items": [{"engine": it["engine"], "problem": it["problem"], "fix": it["fix"]} for it in reversed(items)]}


def import_pack(data):
    """Add fixes from a pack someone shared. The text ends up inside requests to the AI service, so every entry is checked: a fix must be
    nothing but removed/added code lines, text is short and tag-free, and repeats of what is already saved are skipped."""
    if not isinstance(data, dict) or data.get("manimo_fixes") != 1 or not isinstance(data.get("items"), list):
        return {"error": "That is not a Manimo fix pack."}, 400
    added = skipped = 0
    with _lock:
        d = _load()
        for raw in data["items"][:500]:
            if not isinstance(raw, dict) or raw.get("engine") not in ("manim", "manimgx"):
                skipped += 1
                continue
            problem, fix = _clean_text(raw.get("problem"), 700), str(raw.get("fix") or "")
            lines = [ln[:160] for ln in fix.splitlines() if ln.strip()]
            if not problem or not lines or len(lines) > 14 or any(ln[:1] not in "+-" for ln in lines):
                skipped += 1
                continue
            fix = _clean_text("\n".join(lines), 700)
            if any(it["engine"] == raw["engine"] and similarity(it["problem"], problem) >= 0.8 for it in d["items"]):
                skipped += 1
                continue
            d["items"].append({"id": secrets.token_hex(4), "engine": raw["engine"], "problem": problem, "fix": fix, "ts": int(time.time()), "uses": 0, "last_used": 0, "shared": True})
            added += 1
        d["items"] = d["items"][-MAX_ITEMS:]
        _save(d)
    return {"added": added, "skipped": skipped, **stats()}, 200


def prompt_block(items):
    if not items:
        return ""
    parts = []
    for n, it in enumerate(items, 1):
        parts.append(f"{n}. Problem: {it['problem']}\n   What fixed it (- removed, + added):\n" + "\n".join("   " + ln for ln in it["fix"].splitlines()))
    return ("<past_fixes>\nThese fixed similar problems on this PC before. Use one only if it really applies to this code.\n" + "\n".join(parts) + "\n</past_fixes>")
