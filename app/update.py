"""Update check and download from Manimo's GitHub releases.

Only two kinds of request leave the computer: one to the GitHub releases API (to read the newest version) and, when an
update exists, one to download its installer. Nothing about the user or their work is sent. The installer is checked
against the SHA-256 that GitHub publishes for the file before it can be run, and it is never run without a click.
"""
import hashlib
import json
import os
import re
import threading
import time
import urllib.request
from pathlib import Path

REPO = "mathanmj92/manimo"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Manimo" / "data"
UPDATES_DIR = DATA_DIR / "updates"
SETTINGS_FILE = DATA_DIR / "update-settings.json"
CHECK_EVERY = 12 * 3600          # seconds between automatic checks
APP_DIR = Path(__file__).resolve().parent

_lock = threading.Lock()
_state = {"phase": "idle", "current": None, "latest": None, "notes": "", "asset": None, "percent": 0.0, "error": None,
          "path": None, "checked": 0.0, "variant": "lean"}
_cancel = threading.Event()


# ---------------------------------------------------------------- pure helpers (unit-tested)
def parse_version(text):
    """'v1.9.10' -> (1, 9, 10); None if it is not a plain dotted version."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def installer_variant(app_dir=APP_DIR):
    """'full' if this copy came from the installer with Manim CE and LaTeX bundled, else 'lean'.
    Setup writes variant.txt next to the app folder; older installs are told apart by the bundled TeX Live folder."""
    root = Path(app_dir).parent
    try:
        v = (root / "variant.txt").read_text(encoding="utf-8").strip().lower()
        if v in ("lean", "full"):
            return v
    except OSError:
        pass
    return "full" if (root / "texlive").is_dir() else "lean"


def pick_asset(assets, version, variant):
    """The installer to download: the file for this variant, else the plain installer. `assets` is the GitHub API list."""
    v = str(version).lstrip("v")
    wanted = [f"Manimo-Full-Setup-{v}.exe"] if variant == "full" else []
    wanted.append(f"Manimo-Setup-{v}.exe")
    by_name = {a.get("name"): a for a in assets or []}
    for name in wanted:
        if name in by_name:
            return by_name[name]
    return None


def expected_sha256(asset, notes=""):
    """The SHA-256 GitHub published for this file: the API's `digest` field, else a 'name: hash' or 'SHA-256 hash' line in the notes."""
    d = str((asset or {}).get("digest") or "")
    if d.lower().startswith("sha256:"):
        return d.split(":", 1)[1].strip().lower()
    name = (asset or {}).get("name", "")
    for pat in (re.escape(name) + r"\W{1,6}([0-9a-fA-F]{64})", r"SHA-?256\W{1,6}([0-9a-fA-F]{64})"):
        m = re.search(pat, notes or "")
        if m:
            return m.group(1).lower()
    return None


# ---------------------------------------------------------------- settings
def load_settings():
    try:
        s = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        s = {}
    return {"auto_check": s.get("auto_check", True) is not False, "auto_download": s.get("auto_download", True) is not False,
            "skipped": str(s.get("skipped") or "")}


def save_settings(body):
    s = load_settings()
    for k in ("auto_check", "auto_download"):
        if k in body:
            s[k] = bool(body[k])
    if "skipped" in body:
        s["skipped"] = str(body["skipped"] or "")[:20]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(s), encoding="utf-8")
    return s


# ---------------------------------------------------------------- check and download
def _get_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Manimo-update-check"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def status(current):
    with _lock:
        st = dict(_state)
    st["current"] = current
    st["settings"] = load_settings()
    return st


def check(current, force=False):
    """Ask GitHub for the newest release. Fast; safe to call often (it is cached for a while unless forced)."""
    s = load_settings()
    with _lock:
        if _state["phase"] in ("downloading", "ready") and not force:
            return status(current)
        if not force and time.time() - _state["checked"] < 600:
            return status(current)
        _state["current"], _state["variant"] = current, installer_variant()
    try:
        rel = _get_json(API)
    except Exception as exc:
        with _lock:
            _state.update(phase="idle", error=None if not force else "Could not reach GitHub: %s" % (getattr(exc, "reason", None) or exc), checked=time.time())
        return status(current)
    latest = str(rel.get("tag_name") or "").lstrip("v")
    asset = pick_asset(rel.get("assets"), latest, _state["variant"]) if is_newer(latest, current) else None
    with _lock:
        _state.update(latest=latest, notes=str(rel.get("body") or "")[:4000], checked=time.time(), error=None,
                      asset={"name": asset["name"], "size": asset.get("size"), "url": asset.get("browser_download_url"),
                             "sha256": expected_sha256(asset, rel.get("body") or "")} if asset else None)
        if asset and latest != s["skipped"]:
            _state["phase"] = "available"
        else:
            _state["phase"] = "idle"
    return status(current)


def _download(asset):
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPDATES_DIR / asset["name"]
    part = dest.with_suffix(".part")
    try:
        req = urllib.request.Request(asset["url"], headers={"User-Agent": "Manimo-update"})
        h, done, total = hashlib.sha256(), 0, int(asset.get("size") or 0)
        with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
            while True:
                if _cancel.is_set():
                    raise RuntimeError("Cancelled")
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                with _lock:
                    _state["percent"] = round(100.0 * done / total, 1) if total else 0.0
        if total and done != total:
            raise RuntimeError("The download was cut short (%d of %d bytes). Try again." % (done, total))
        want = asset.get("sha256")
        if not want:
            raise RuntimeError("GitHub did not publish a checksum for this file, so it was not kept. Download the installer from the website instead.")
        if h.hexdigest().lower() != want.lower():
            raise RuntimeError("The downloaded file does not match its published checksum, so it was deleted. Try again.")
        os.replace(part, dest)
        with _lock:
            _state.update(phase="ready", percent=100.0, path=str(dest), error=None)
    except Exception as exc:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
        with _lock:
            _state.update(phase="available", error=str(exc) if str(exc) != "Cancelled" else None, percent=0.0)


def start_download():
    with _lock:
        asset = _state.get("asset")
        if _state["phase"] == "downloading":
            return {"ok": True}
        if not asset or not asset.get("url"):
            return {"error": "There is no update to download."}
        _state.update(phase="downloading", percent=0.0, error=None)
    _cancel.clear()
    threading.Thread(target=_download, args=(dict(asset),), daemon=True).start()
    return {"ok": True}


def cancel_download():
    _cancel.set()
    return {"ok": True}


def install():
    """Start the downloaded installer (its normal window). The caller then quits Manimo so Setup can replace its files."""
    with _lock:
        path = _state.get("path")
        ok = _state["phase"] == "ready" and path and Path(path).is_file()
    if not ok:
        return {"error": "The update has not finished downloading."}
    if os.name == "nt":
        os.startfile(path)  # noqa: S606 - starts the installer the user just chose to run
    return {"ok": True}


def handle(method, path, body, current):
    """Routes used by server.py: returns (payload, status)."""
    if path == "/api/update/status":
        return status(current), 200
    if path == "/api/update/check":
        return check(current, force=bool(body.get("force"))), 200
    if path == "/api/update/download":
        return start_download(), 200
    if path == "/api/update/cancel":
        return cancel_download(), 200
    if path == "/api/update/install":
        return install(), 200
    if path == "/api/update/settings":
        return {"settings": save_settings(body or {})}, 200
    if path == "/api/update/skip":
        save_settings({"skipped": body.get("version")})
        with _lock:
            _state["phase"] = "idle"
        return status(current), 200
    return {"error": "not found"}, 404
