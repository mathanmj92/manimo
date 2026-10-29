#!/usr/bin/env python3
"""Manimo - local render server.

Serves the Manimo UI on 127.0.0.1 and runs the render engines as child processes:
  * ManimGX  (`python -m manimgx`)   - the default, GPU based
  * Manim CE (`python -m manim`)     - optional, installed on request
Standard library only, so it starts even before an engine is installed.
"""
import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ai
import project
import voice
from pathlib import Path
from urllib.request import urlopen

APP_DIR = Path(__file__).resolve().parent
VERSION = "1.9.5"
FIRST_PORT = 8765
PORT_SPAN = 11
IDLE_EXIT_SECONDS = 120
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
TOKEN = secrets.token_urlsafe(24)
TIMES_FILE = Path.home() / ".manimgx-studio" / "render-times.json"

RESOLUTION = {"l": "854x480", "m": "1280x720", "h": "1920x1080", "k": "3840x2160"}
SHORT_SIDE = {"l": 480, "m": 720, "h": 1080, "k": 2160}      # the video's shorter side at each quality
SHAPES = {"16:9": (16, 9), "9:16": (9, 16), "1:1": (1, 1), "4:3": (4, 3), "3:4": (3, 4)}
CODE_PAIR = re.compile(r"pixel_width[^=\n]*?pixel_height[^=\n]*=\s*(\d{3,5})\s*,\s*(\d{3,5})")
CODE_WIDTH = re.compile(r"pixel_width\W*=\s*(\d{3,5})")
CODE_HEIGHT = re.compile(r"pixel_height\W*=\s*(\d{3,5})")


def code_shape(code):
    """The proportions a scene asks for in its own code (config.pixel_width, config.pixel_height = 1080, 1920), or None."""
    pair = CODE_PAIR.search(code or "")
    if pair:
        return int(pair.group(1)), int(pair.group(2))
    w, h = CODE_WIDTH.search(code or ""), CODE_HEIGHT.search(code or "")
    if w and h:
        return int(w.group(1)), int(h.group(1))
    return None

def video_size(quality, shape, code=""):
    """(width, height) for a quality and a shape: 'auto' follows the code, else 16:9. The shorter side is the quality."""
    if shape in SHAPES:
        a, b = SHAPES[shape]
    else:
        a, b = code_shape(code) or (16, 9)
    short = SHORT_SIDE.get(quality, 1080)
    if a >= b:
        return int(round(short * a / b / 2) * 2), short
    return short, int(round(short * b / a / 2) * 2)
PRESET = {"fast": "veryfast", "balanced": "medium", "small": "slow"}  # ManimGX encoder speed vs file size
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CLASS_DEF = re.compile(r"^class\s+(\w+)\s*\(([^)]*)\)\s*:", re.M)
SCENE_BASE = re.compile(r"(^|\.)\w*Scene\w*$")
RESULT = re.compile(r"([\d.]+)\s*s,\s*(\d+x\d+)\s+at\s+(\d+)\s*fps")
# "[12] t=91.6s (scene.py:357)  cap (Text '...') and volt[0] (Rectangle): Rectangle runs through the text"
LAYOUT = re.compile(r"^\[(\d+)\]\s+t=(\S+)\s+\(scene\.py:(\d+)\)\s+(.*)$")
ERRLINE = re.compile(r'scene\.py(?:"?,\s*line\s+|:)(\d+)')
CE_PROGRESS = re.compile(r"Animation\s+(\d+):\s*(.*?)\s+(\d+)%\|[^|]*\|\s*(\d+)/(\d+)")
STEP_CALLS = re.compile(r"self\.(?:play|wait)\(")
PREVIEW_TYPES = {".mp4", ".webm", ".html", ".png", ".jpg", ".jpeg", ".gif", ".srt", ".vtt", ".pdf", ".wav", ".mp3", ".m4a", ".ogg", ".mov", ".mkv"}   # what the preview may load
OPEN_URLS = {
    "https://mathanmj92.github.io/mathan/",
    "https://manimgx.academa.ai/",
    "https://docs.manim.community/",
    "https://console.anthropic.com/settings/keys",
    "https://docs.manim.community/en/stable/index.html",
    "https://github.com/ManimCommunity/manim",
    "https://github.com/3b1b/manim",
    "https://3blue1brown.com/faq",
    "https://www.youtube.com/@3blue1brown",
    "https://www.youtube.com/results?search_query=How+I+animate+3Blue1Brown+Manim+demo",
    "https://www.youtube.com/results?search_query=manim+community+edition+tutorial+for+beginners",
    "https://www.youtube.com/results?search_query=manim+python+math+animation+tutorial",
    "https://www.youtube.com/results?search_query=manimgx",
}

HINTS = [
    ("ModuleNotFoundError", "The code imports a package that is not installed."),
    ("SyntaxError", "The code has a syntax error."),
    ("IndentationError", "The code has an indentation problem."),
    ("NameError", "The code uses a name that is not defined. Did you forget the import line at the top?"),
    ("AttributeError", "The code uses something that does not exist on that object."),
    ("latex", "This scene needs LaTeX (MathTex / Tex), which is not installed on this PC. Run the Manimo installer again and tick \"Manim Community Edition and LaTeX\"."),
    ("LaTeX", "This scene needs LaTeX (MathTex / Tex), which is not installed on this PC. Run the Manimo installer again and tick \"Manim Community Edition and LaTeX\"."),
]

_lock = threading.Lock()
_job = {"state": "idle"}
_proc = None
_install = {"state": "idle", "log": []}
_served = {}                       # random id -> directory whose files the preview may load
_last_ping = time.time()
_pinged = False
_pending_project = None   # a project.mo the user double-clicked while Manimo was already open
HOOKS = {"focus": [], "quit": []}   # the desktop window registers callbacks here


# ---------------------------------------------------------------- engines
def version_of(dist):
    if importlib.util.find_spec(dist) is None:
        return None
    try:
        from importlib.metadata import version
        return version("manimgx" if dist == "manimgx" else "manim")
    except Exception:
        return "unknown"


def engines():
    return {"manimgx": version_of("manimgx"), "manim": version_of("manim")}


def bundled_texlive_bin(python_exe=None):
    """The LaTeX tools that the installer's optional 'Manim Community Edition and LaTeX' component put next to the private
    Python ({app}\\python\\python.exe -> {app}\\texlive\\bin\\windows), or None when that component is not installed."""
    base = Path(python_exe or sys.executable).resolve().parent.parent
    bindir = base / "texlive" / "bin" / "windows"
    return bindir if (bindir / "latex.exe").is_file() and (bindir / "dvisvgm.exe").is_file() else None


def tex_env(env, bindir):
    """A copy of env in which the bundled LaTeX comes first on PATH. It is only ever handed to a render process, so the
    user's own PATH and settings are never touched. Variables that could redirect the bundled TeX to another tree are dropped."""
    out = dict(env)
    if bindir:
        out["PATH"] = str(bindir) + os.pathsep + out.get("PATH", "")
        for name in ("TEXMFCNF", "TEXMFHOME", "TEXINPUTS", "TEXMFLOCAL", "TEXMFVAR", "TEXMFCONFIG"):
            out.pop(name, None)
    return out


def parse_latex_version(text):
    """First line of `latex --version`, for example 'pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)' -> 'pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)'."""
    for line in (text or "").splitlines():
        line = line.strip()
        if re.search(r"\d+\.\d+", line) and re.search(r"TeX", line, re.I):
            return line[:120]
    return None


_latex_cache = {}


def latex_info():
    """{"found", "bundled", "version"} for the LaTeX that Manim CE would use (the bundled one first, else one on PATH)."""
    bindir = bundled_texlive_bin()
    path = tex_env(os.environ, bindir).get("PATH")
    exe = shutil.which("latex", path=path)
    if not exe:
        return {"found": False, "bundled": False, "version": None}
    if exe not in _latex_cache:
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW,
                                 env=tex_env(os.environ, bindir), stdin=subprocess.DEVNULL).stdout
        except Exception:
            out = ""
        _latex_cache[exe] = parse_latex_version(out)
    return {"found": True, "bundled": bool(bindir), "version": _latex_cache[exe]}


def pick_engine(code):
    """Which engine the code is written for, from its import line."""
    if re.search(r"^\s*(?:from|import)\s+manimgx\b", code, re.M):
        return "manimgx"
    if re.search(r"^\s*(?:from|import)\s+manim\b", code, re.M):
        return "manim"
    return "manimgx"


def find_scenes(code):
    """Names of classes that derive (directly or via a mixin list) from something called *Scene*."""
    names = []
    for m in CLASS_DEF.finditer(code):
        bases = [b.strip() for b in m.group(2).split(",")]
        if any(SCENE_BASE.search(b) for b in bases):
            names.append(m.group(1))
    return names


def scene_source(code, scene):
    """The text of one class, to estimate how many animations it plays."""
    spans = [(m.start(), m.group(1)) for m in CLASS_DEF.finditer(code)]
    for i, (start, name) in enumerate(spans):
        if name == scene:
            end = spans[i + 1][0] if i + 1 < len(spans) else len(code)
            return code[start:end]
    return code


def default_output_dir():
    videos = Path.home() / "Videos"
    base = videos if videos.exists() else Path.home()
    return str(base / "Manimo")


def load_times():
    try:
        return json.loads(TIMES_FILE.read_text())
    except Exception:
        return {}


def save_time(key, seconds):
    times = load_times()
    times[key] = round(seconds, 2)
    try:
        TIMES_FILE.parent.mkdir(parents=True, exist_ok=True)
        TIMES_FILE.write_text(json.dumps(times))
    except OSError:
        pass


def time_key(opts, scene):
    raw = f"{opts['code']}|{scene}|{opts['kind']}|{opts['engine']}|{opts['quality']}|{opts['fps']}|{opts['encoding']}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------- job state
def public_job():
    with _lock:
        j = dict(_job)
        j["items"] = [dict(i) for i in j.get("items", [])]
    if j.get("state") == "running":
        j["elapsed"] = time.time() - j["started"]
    j.pop("started", None)
    j["log"] = j.get("log", [])[-120:]
    return j


def update_job(**kw):
    with _lock:
        _job.update(kw)


def update_item(index, **kw):
    with _lock:
        if index < len(_job.get("items", [])):
            _job["items"][index].update(kw)


def is_cancelled():
    with _lock:
        return _job.get("state") == "cancelled"


def kill_tree(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, creationflags=NO_WINDOW)
        else:
            proc.kill()
    except Exception:
        pass


def friendly_error(lines):
    text = "\n".join(lines[-80:])
    for needle, msg in HINTS:
        if needle in text:
            return msg
    return "The engine stopped before the video was finished."


def unique_path(directory, name):
    dest = Path(directory) / name
    stem, suffix, n = dest.stem, dest.suffix, 2
    while dest.exists():
        dest = Path(directory) / f"{stem}_{n}{suffix}"
        n += 1
    return dest


def serve_dir(directory):
    """Let the preview load files from this folder; returns the id used in /files/<id>/<name>."""
    directory = str(Path(directory))
    for key, value in _served.items():
        if value == directory:
            return key
    key = secrets.token_urlsafe(9)
    _served[key] = directory
    return key


def file_entry(path, kind, name=None):
    p = Path(path)
    return {"name": name or p.name, "path": str(p), "kind": kind, "size": p.stat().st_size if p.exists() else 0,
            "url": f"/files/{serve_dir(p.parent)}/{p.name}"}


# ---------------------------------------------------------------- rendering
def build_command(opts, scene, src, video, work):
    py = sys.executable
    if opts["engine"] == "manim":
        cmd = [py, "-m", "manim", "render", str(src), scene, f"-q{opts['quality']}", "--media_dir", str(work / "media"),
               "--progress_bar", "display", "--disable_caching"]
        cmd += ["-r", opts["resolution"].replace("x", ",")]
        if opts["fps"] != "auto":
            cmd += ["--fps", str(opts["fps"])]
        return cmd
    # run_with_voice.py is `python -m manimgx` with Manimo's offline narration voice as the default voice
    cmd = [py, str(APP_DIR / "run_with_voice.py"), "--voice", opts.get("voice", "am_adam"), "--speed", str(opts.get("speed", 1.0)),
           "present" if opts["kind"] == "present" else "render", str(src), scene,
           "-o", str(video), "-r", opts["resolution"]]
    cmd += ["--no-open"] if opts["kind"] == "present" else ["--preset", PRESET[opts["encoding"]]]
    if opts["fps"] != "auto":
        cmd += ["--fps", str(opts["fps"])]
    return cmd


def run_scene(opts, scene, index, count, expected):
    """Render (or present) one scene. ManimGX prints nothing until it finishes and renders fast, so its progress is an
    estimate (last run's time for this scene, or a gentle curve the first time). Manim CE reports animations as it
    goes, so its progress is measured. Returns {"ok", "outputs", "error", "warnings", "info", "elapsed"}."""
    global _proc
    out_dir = Path(opts["out_dir"])
    work = out_dir / ".manimo-work" / f"{opts['id']}-{index}"
    lines = []
    present = opts["kind"] == "present"
    ce = opts["engine"] == "manim"
    prog = {"seen": False, "idx": 0, "frac": 0.0}
    est_total = max(1, len(STEP_CALLS.findall(scene_source(opts["code"], scene))))
    try:
        work.mkdir(parents=True, exist_ok=True)
        src = work / "scene.py"
        src.write_text(opts["code"], encoding="utf-8")
        video = work / f"{scene}.mp4"
        cmd = build_command(opts, scene, src, video, work)
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        if ce:
            env = tex_env(env, bundled_texlive_bin())
        proc = subprocess.Popen(cmd, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        _proc = proc

        def handle(line):
            if not line:
                return
            m = CE_PROGRESS.search(line) if ce else None
            if m:
                prog.update(seen=True, idx=int(m.group(1)), frac=int(m.group(4)) / max(int(m.group(5)), 1))
                return
            lines.append(line)
            with _lock:
                _job.setdefault("log", []).append(line)
                del _job["log"][:-300]

        def reader():
            pending = ""
            while True:
                chunk = proc.stdout.read1(4096)
                if not chunk:
                    break
                pending += ANSI.sub("", chunk.decode("utf-8", "replace"))
                parts = re.split(r"[\r\n]+", pending)
                pending = parts.pop()
                for part in parts:
                    handle(part.strip())
            handle(pending.strip())

        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()

        t0 = time.time()
        later = [expected.get(s) for s in opts["scenes"][index + 1:]]
        while proc.poll() is None:
            el = time.time() - t0
            exp = expected.get(scene)
            if prog["seen"]:
                total = max(est_total, prog["idx"] + 1)
                spct = min(97.0, 100.0 * (prog["idx"] + prog["frac"]) / total)
                left = el * (100 - spct) / spct if spct >= 4 else None
            elif exp:
                spct, left = min(95.0, 100.0 * el / max(exp, 0.5)), max(exp - el, 1.0)
            else:
                spct, left = 95.0 * (1 - math.exp(-el / 40.0)), None  # first run of a scene: no history yet
            eta = None if left is None or any(x is None for x in later) else left + sum(later)
            spct = max(spct, prog.get("shown", 0.0))     # never move backwards when the estimate is replaced by real progress
            prog["shown"] = spct
            update_item(index, percent=spct)
            update_job(percent=100.0 * (index + spct / 100.0) / count, eta=eta)
            time.sleep(0.3)
        reader_thread.join(timeout=3)
        elapsed = time.time() - t0

        if is_cancelled():
            return {"ok": False, "cancelled": True}
        warnings = []
        for line in lines:
            m = LAYOUT.match(line)
            if m:
                warnings.append({"scene": scene, "line": int(m.group(3)), "t": m.group(2), "text": m.group(4)})
        info = {}
        for line in lines:
            m = RESULT.search(line)
            if m:
                info = {"video_seconds": float(m.group(1)), "resolution": m.group(2), "fps": int(m.group(3))}
        if ce and proc.returncode == 0:   # Manim CE chooses its own folders: find the finished file
            found = [f for f in (work / "media").rglob(f"{scene}.mp4") if "partial_movie_files" not in f.parts]
            if found:
                video = found[0]
        if proc.returncode != 0 or not video.exists():
            err_line = None
            for line in lines:
                m = ERRLINE.search(line)
                if m:
                    err_line = int(m.group(1))
            return {"ok": False, "elapsed": elapsed, "warnings": warnings,
                    "error": {"title": friendly_error(lines), "detail": "\n".join(lines[-40:]), "line": err_line}}

        save_time(time_key(opts, scene), elapsed)
        out_dir.mkdir(parents=True, exist_ok=True)
        if present:
            folder = unique_path(out_dir, f"{scene}_slides")
            folder.mkdir(parents=True)
            moved = []
            for f in work.iterdir():
                if f.name != "scene.py" and f.is_file() and f.suffix in (".mp4", ".html", ".pdf", ".srt"):
                    shutil.move(str(f), str(folder / f.name))
                    moved.append(folder / f.name)
            page = next((p for p in moved if p.suffix == ".html"), None)
            outputs = [file_entry(page, "slides", f"{scene} slideshow")] if page else []
            outputs += [file_entry(p, "video") for p in moved if p.suffix == ".mp4"]
        else:
            if opts.get("dest_stem"):        # a project keeps one render per scene, under a steady name
                dest = out_dir / f"{opts['dest_stem']}__{scene}.mp4"
                os.replace(video, dest)
                subs = video.with_suffix(".srt")
                if subs.is_file():
                    os.replace(subs, dest.with_suffix(".srt"))
            else:
                dest = unique_path(out_dir, f"{scene}.mp4")
                shutil.move(str(video), str(dest))
            outputs = [file_entry(dest, "video")]
        return {"ok": True, "outputs": outputs, "warnings": warnings, "info": info, "elapsed": elapsed}
    except Exception as exc:  # surface anything unexpected in the UI instead of dying silently
        return {"ok": False, "error": {"title": "Could not start the render.", "detail": repr(exc), "line": None}}
    finally:
        _proc = None
        shutil.rmtree(work, ignore_errors=True)


def run_batch(opts):
    out_dir = Path(opts["out_dir"])
    scenes = opts["scenes"]
    times = load_times()
    expected = {s: times.get(time_key(opts, s)) for s in scenes}
    outputs, warnings, failures = [], [], []
    info = {}
    try:
        for i, scene in enumerate(scenes):
            if is_cancelled():
                break
            with _lock:
                _job["current"] = i
                _job["scene"] = scene
            update_item(i, state="running", percent=0.0)
            with _lock:
                _job.setdefault("log", []).append(f"--- {scene} ---")
            res = run_scene(opts, scene, i, len(scenes), expected)
            if res.get("cancelled"):
                update_item(i, state="cancelled")
                break
            warnings += res.get("warnings", [])
            if res["ok"]:
                outputs += res["outputs"]
                info = res.get("info") or info
                if opts.get("project_file") and res["outputs"]:
                    project.record_render(opts["project_file"], scene, project.scene_hash(opts["code"], scene, opts), res["outputs"][0]["path"],
                                          (res.get("info") or {}).get("video_seconds"))
                update_item(i, state="done", percent=100.0, outputs=res["outputs"], seconds=res["elapsed"],
                            video_seconds=(res.get("info") or {}).get("video_seconds"))
                update_job(outputs=list(outputs), warnings=list(warnings))
            else:
                failures.append((scene, res["error"]))
                update_item(i, state="error", error=res["error"])
        with _lock:
            cancelled = _job.get("state") == "cancelled"
        if cancelled:
            return
        if len(failures) == len(scenes):
            scene, err = failures[-1]
            update_job(state="error", error=dict(err, scene=scene), warnings=warnings, **info)
        else:
            update_job(state="done", percent=100.0, eta=0, outputs=outputs, warnings=warnings,
                       failed=[{"scene": s, "error": e} for s, e in failures], **info)
    except Exception as exc:
        update_job(state="error", error={"title": "The render queue stopped unexpectedly.", "detail": repr(exc), "line": None})
    finally:
        try:
            (out_dir / ".manimo-work").rmdir()
        except OSError:
            pass


def start_job(body):
    code = str(body.get("code", ""))
    if not code.strip():
        return {"error": "There is no code to render."}, 400
    engine = pick_engine(code)
    if engines()[engine] is None:
        if engine == "manim":
            return {"error": "This code is written for Manim (Community Edition), which is not installed yet."}, 409
        return {"error": "The ManimGX engine is not installed. Re-run the installer to repair."}, 409
    found = find_scenes(code)
    if not found:
        return {"error": "No Scene class found in the code."}, 400
    kind = "present" if body.get("kind") == "present" else "render"
    if kind == "present" and engine != "manimgx":
        return {"error": "Present works with ManimGX code only."}, 400
    wanted = body.get("scenes")
    if isinstance(wanted, list) and wanted:
        scenes = [s for s in found if s in wanted]
    else:
        scenes = [body.get("scene")] if body.get("scene") in found else [found[-1]]
    if kind == "present":
        scenes = scenes[:1]
    if not scenes:
        return {"error": "None of the chosen scenes exist in the code."}, 400
    with _lock:
        if _job.get("state") == "running":
            return {"error": "A render is already running."}, 409
    quality, fps, encoding = body.get("quality", "h"), body.get("fps", "auto"), body.get("encoding", "balanced")
    opts = {
        "id": secrets.token_hex(4),
        "code": code,
        "engine": engine,
        "scenes": scenes,
        "kind": kind,
        "quality": quality if quality in RESOLUTION else "h",
        "shape": body.get("shape") if body.get("shape") in SHAPES else "auto",
        "fps": fps if fps in (30, 60) else "auto",
        "encoding": encoding if encoding in PRESET else "balanced",
        "out_dir": str(body.get("out_dir") or default_output_dir()),
        "voice": body.get("voice") if body.get("voice") in voice.VOICES else voice.DEFAULT_VOICE,
        "speed": voice._clean(None, body.get("speed"))[1],
    }
    opts["resolution"] = "%dx%d" % video_size(opts["quality"], opts["shape"], code)
    if body.get("project_file") and project.current() and kind == "render":
        pf = Path(str(body["project_file"])).name
        opts.update(out_dir=str(project.renders_dir()), project_file=pf, dest_stem=Path(pf).stem)
    update_job(**{"state": "running", "started": time.time(), "percent": 0.0, "eta": None, "log": [],
                  "outputs": [], "warnings": [], "failed": [], "error": None, "kind": kind, "engine": engine,
                  "scene": scenes[0], "scenes": found, "current": 0,
                  "items": [{"scene": s, "state": "queued", "percent": 0.0} for s in scenes],
                  "out_dir": opts["out_dir"], "resolution": opts["resolution"],
                  "fps": None if opts["fps"] == "auto" else opts["fps"], "video_seconds": None})
    threading.Thread(target=run_batch, args=(opts,), daemon=True).start()
    return {"ok": True, "count": len(scenes), "engine": engine}, 200


def cancel_job():
    with _lock:
        running = _job.get("state") == "running"
        if running:
            _job["state"] = "cancelled"
    if running and _proc is not None:
        kill_tree(_proc)
    return {"ok": True}, 200


# ---------------------------------------------------------------- adding Manim (Community Edition) on request
def run_install(package):
    cmd = [sys.executable, "-m", "pip", "install", package, "--disable-pip-version-check", "--progress-bar", "off",
           "--retries", "8", "--timeout", "25"]       # patient: slow or flaky connections are common
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                creationflags=NO_WINDOW)
        for raw in iter(proc.stdout.readline, b""):
            line = ANSI.sub("", raw.decode("utf-8", "replace")).strip()
            if line:
                with _lock:
                    _install["log"].append(line)
                    del _install["log"][:-200]
                    _install["step"] = line[:110]
        code = proc.wait()
    except Exception as exc:
        code = 1
        with _lock:
            _install["log"].append(repr(exc))
    importlib.invalidate_caches()
    with _lock:
        if code == 0 and engines()["manim"]:
            _install["state"] = "done"
        else:
            _install["state"] = "error"
            _install["error"] = ("Could not download Manim. Check your internet connection and try again."
                                 if code else "Manim installed but could not be loaded.")


def start_install(body):
    if body.get("engine") != "manim":
        return {"error": "Unknown engine."}, 400
    with _lock:
        if _install.get("state") == "running":
            return {"error": "An install is already running."}, 409
        _install.clear()
        _install.update({"state": "running", "log": [], "step": "Contacting the package index...", "started": time.time()})
    threading.Thread(target=run_install, args=("manim",), daemon=True).start()
    return {"ok": True}, 200


# ---------------------------------------------------------------- system helpers
def pick_folder(body):
    start = str(body.get("path") or default_output_dir())
    title = str(body.get("title") or "Choose output folder")[:80]
    script = (
        "import tkinter as tk\nfrom tkinter import filedialog\n"
        "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
        f"p = filedialog.askdirectory(initialdir={start!r}, title={title!r})\n"
        "print(p or '')\n"
    )
    try:
        out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                             creationflags=NO_WINDOW, timeout=300).stdout.strip()
    except Exception:
        out = ""
    return {"path": os.path.normpath(out) if out else None}, 200


def open_path(body, must_be_dir):
    target = Path(str(body.get("path", "")))
    if must_be_dir:
        target.mkdir(parents=True, exist_ok=True)
    else:
        allowed = {o["path"] for o in _job.get("outputs", [])}
        if str(target) not in allowed:
            return {"error": "That file is not part of the last render."}, 403
    if not target.exists():
        return {"error": "Path no longer exists."}, 404
    if os.name == "nt":
        os.startfile(str(target))  # noqa: S606 - local desktop app opening the user's own file
    else:
        subprocess.Popen(["xdg-open", str(target)])
    return {"ok": True}, 200


def serve_file(body):
    """Make an earlier render (from the Recent renders list) playable in the preview."""
    target = Path(str(body.get("path", "")))
    if not target.is_file() or target.suffix.lower() not in PREVIEW_TYPES:
        return {"error": "That file is gone or cannot be previewed."}, 404
    return {"url": f"/files/{serve_dir(target.parent)}/{target.name}"}, 200


VIDEO_TYPES = (".mp4", ".mov", ".webm", ".mkv")
THUMB_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Manimo" / "data" / "thumbs"


def library_list(body):
    """The finished videos in a folder (newest first), for the video library. Nothing is probed here: each card asks for its own picture."""
    folder = Path(str(body.get("dir") or default_output_dir()))
    if not folder.is_dir():
        return {"dir": str(folder), "videos": []}, 200
    items = []
    for f in folder.iterdir():
        if f.is_file() and f.suffix.lower() in VIDEO_TYPES and not f.name.startswith("."):
            st = f.stat()
            items.append({"name": f.name, "path": str(f), "size": st.st_size, "mtime": st.st_mtime})
    items.sort(key=lambda i: -i["mtime"])
    return {"dir": str(folder), "videos": items[:120], "total": len(items)}, 200


def video_meta(body):
    """A video's length, size and a cover picture (made once, kept in the data folder)."""
    src = Path(str(body.get("path", "")))
    if not src.is_file() or src.suffix.lower() not in VIDEO_TYPES:
        return {"error": "That video is gone."}, 404
    ff = ffmpeg_exe()
    if not ff:
        return {"error": "The video tool (ffmpeg) is missing."}, 500
    st = src.stat()
    key = hashlib.sha1(f"{src}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()[:16]
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    thumb, seek = THUMB_DIR / f"{key}.jpg", None
    p = subprocess.run([ff, "-hide_banner", "-i", str(src)], capture_output=True, text=True, creationflags=NO_WINDOW)
    text = p.stderr or ""
    d = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    seconds = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0.0
    size = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", text)
    at = body.get("at")
    if isinstance(at, (int, float)) and at >= 0:                 # a cover picked by the user
        thumb, seek = THUMB_DIR / f"{key}-{int(at * 10)}.jpg", float(at)
    if not thumb.is_file():
        seek = seek if seek is not None else min(max(seconds * 0.4, 0.0), 8.0)     # a moment in, past any fade from black
        subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{seek:.2f}", "-i", str(src), "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(thumb)],
                       capture_output=True, creationflags=NO_WINDOW, timeout=60)
    out = {"seconds": round(seconds, 2), "width": int(size.group(1)) if size else None, "height": int(size.group(2)) if size else None}
    if thumb.is_file():
        out["thumb"] = f"/files/{serve_dir(THUMB_DIR)}/{thumb.name}"
    return out, 200


def open_url(body):
    url = str(body.get("url", ""))
    if url not in OPEN_URLS:
        return {"error": "That link is not allowed."}, 403
    webbrowser.open(url)
    return {"ok": True}, 200


def quit_app():
    for fn in HOOKS["quit"]:
        threading.Thread(target=fn, daemon=True).start()
    return {"ok": True}, 200


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "Manimo/" + VERSION

    def log_message(self, *args):
        pass

    def _host_ok(self):
        host = (self.headers.get("Host") or "").lower()
        port = self.server.server_address[1]
        return host in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _send(self, payload, status=200, ctype="application/json", extra=None):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path, ctype):
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2)))
                end = min(end, size - 1)
                if start > end:
                    return self._send({"error": "bad range"}, 416, extra={"Content-Range": f"bytes */{size}"})
                status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    chunk = f.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        global _last_ping, _pinged
        if not self._host_ok():
            return self._send({"error": "bad host"}, 403)
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            html = (APP_DIR / "index.html").read_text(encoding="utf-8").replace("__MANIMGX_TOKEN__", TOKEN)
            return self._send(html.encode("utf-8"), ctype="text/html; charset=utf-8")
        if path.startswith("/vendor/") and path.endswith(".js") and "/" not in path[len("/vendor/"):]:
            asset = APP_DIR / "vendor" / path[len("/vendor/"):]
            if asset.is_file():
                return self._send(asset.read_bytes(), ctype="text/javascript; charset=utf-8")
        if path.startswith("/assets/") and "/" not in path[len("/assets/"):]:
            asset = APP_DIR / "assets" / path[len("/assets/"):]
            if asset.suffix in (".css", ".js", ".svg", ".png", ".ico", ".json") and asset.is_file():
                return self._send(asset.read_bytes(), ctype=(mimetypes.guess_type(asset.name)[0] or "application/octet-stream") + "; charset=utf-8"
                                  if asset.suffix in (".css", ".js", ".svg", ".json") else mimetypes.guess_type(asset.name)[0] or "application/octet-stream")
        if path.startswith("/files/"):
            parts = path.split("/")
            if len(parts) == 4 and parts[2] in _served:
                name = parts[3]
                target = Path(_served[parts[2]]) / name
                if name == Path(name).name and Path(name).suffix.lower() in PREVIEW_TYPES and target.is_file():
                    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
                    return self._send_file(target, ctype)
            return self._send({"error": "not found"}, 404)
        if path == "/api/ping":
            _last_ping, _pinged = time.time(), True
            return self._send({"app": "manimgx", "version": VERSION})
        if path == "/api/pending":
            global _pending_project
            p, _pending_project = _pending_project, None
            return self._send({"open_project": p})
        if path == "/api/focus":
            if "project=" in self.path:
                from urllib.parse import urlparse, parse_qs
                _pending_project = (parse_qs(urlparse(self.path).query).get("project") or [None])[0]
            for fn in HOOKS["focus"]:
                threading.Thread(target=fn, daemon=True).start()
            return self._send({"ok": True})
        if path == "/api/status":
            tex = latex_info()
            return self._send({
                "app": "manimgx", "version": VERSION, "engines": engines(), "engine": engines()["manimgx"], "voice": voice.status(),
                "python": sys.version.split()[0], "python_path": sys.executable, "out_dir": default_output_dir(),
                "latex": tex["found"], "latex_bundled": tex["bundled"], "latex_version": tex["version"],
            })
        if path == "/api/job":
            return self._send(public_job())
        if path.startswith("/api/project"):
            payload, status = project.handle("GET", path, {})
            return self._send(payload, status)
        if path.startswith("/api/ai/"):
            payload, status = ai.handle("GET", path, {})
            return self._send(payload, status)
        if path == "/api/install":
            with _lock:
                j = dict(_install)
            j["log"] = j.get("log", [])[-60:]
            if j.get("state") == "running":
                j["elapsed"] = time.time() - j["started"]
            return self._send(j)
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Token") != TOKEN:
            return self._send({"error": "forbidden"}, 403)
        length = int(self.headers.get("Content-Length") or 0)
        if self.path.startswith("/api/record"):
            payload, status = save_recording(self.path, self.rfile, length)
            return self._send(payload, status)
        if self.path.startswith("/api/project/recording"):
            try:
                from urllib.parse import urlparse, parse_qs
                q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                return self._send(project.save_upload(q.get("name"), self.rfile, length, convert=q.get("convert")), 200)
            except (ValueError, OSError) as exc:
                return self._send({"error": str(exc)}, 400)
        if length > 2_000_000:
            return self._send({"error": "too large"}, 413)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send({"error": "bad json"}, 400)
        if self.path.startswith("/api/ai/"):
            payload, status = ai.handle("POST", self.path, body)
            return self._send(payload, status)
        if self.path == "/api/project/import-pick":
            payload, status = pick_media()
            return self._send(payload, status)
        if self.path.startswith("/api/project"):
            payload, status = project.handle("POST", self.path, body)
            return self._send(payload, status)
        routes = {
            "/api/render": lambda: start_job(body),
            "/api/cancel": cancel_job,
            "/api/install-engine": lambda: start_install(body),
            "/api/pick-folder": lambda: pick_folder(body),
            "/api/voice/preview": lambda: voice_preview(body),
            "/api/report-save": lambda: report_save(body),
            "/api/mailto": lambda: open_mail(body),
            "/api/script": lambda: script_lines(body),
            "/api/script-save": lambda: script_save(body),
            "/api/open-folder": lambda: open_path(body, True),
            "/api/open-file": lambda: open_path(body, False),
            "/api/open-url": lambda: open_url(body),
            "/api/serve-file": lambda: serve_file(body),
            "/api/library": lambda: library_list(body),
            "/api/video-meta": lambda: video_meta(body),
            "/api/quit": quit_app,
        }
        handler = routes.get(self.path)
        if handler is None:
            return self._send({"error": "not found"}, 404)
        payload, status = handler()
        self._send(payload, status)


def script_lines(body):
    """What the chosen scene says and when (estimated: no voice is used)."""
    code, scene = str(body.get("code", "")), str(body.get("scene", ""))
    if pick_engine(code) != "manimgx":
        return {"lines": [], "end": 0, "note": "Narration lines are read from ManimGX code that uses self.say(...)."}, 200
    found = find_scenes(code)
    if scene not in found:
        scene = found[-1] if found else ""
    if not scene:
        return {"error": "No Scene class found in the code."}, 400
    tmp = Path(tempfile.mkdtemp(prefix="manimo-script-"))
    try:
        (tmp / "scene.py").write_text(code, encoding="utf-8")
        vname = body.get("voice") if body.get("voice") in voice.VOICES else voice.DEFAULT_VOICE
        p = subprocess.run([sys.executable, str(APP_DIR / "scriptdump.py"), "scene.py", scene, vname, str(voice._clean(None, body.get("speed"))[1])],
                           cwd=str(tmp), capture_output=True, text=True, timeout=240, creationflags=NO_WINDOW)
        try:
            data = json.loads((p.stdout.strip().splitlines() or ["{}"])[-1])
        except ValueError:
            data = {"error": (p.stderr or "The scene could not be read.")[-300:]}
        if data.get("error"):
            return {"error": "Could not read the scene: " + data["error"]}, 400
        data["scene"] = scene
        if not data["lines"]:
            data["note"] = "This scene has no narration. Add lines with self.say(\"...\")."
        return data, 200
    except subprocess.TimeoutExpired:
        return {"error": "Reading the scene took too long."}, 500
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _stamp(t, sep="."):
    t = max(0.0, t)
    return "%02d:%02d%s%d" % (int(t // 60), int(t % 60), sep, int((t * 10) % 10))


def _clock(t, comma):
    t = max(0.0, t)
    ms = int(round(t * 1000))
    return "%02d:%02d:%02d%s%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, "," if comma else ".", ms % 1000)


def script_text(lines, fmt, end, est=True):
    lines = [{"t": float(l["t"]), "text": str(l["text"]), "dur": float(l.get("dur", 2))} for l in lines]
    ends = [min(l["t"] + l["dur"], lines[i + 1]["t"]) if i + 1 < len(lines) else l["t"] + l["dur"] for i, l in enumerate(lines)]
    if fmt == "json":
        return json.dumps({"lines": [{"start": l["t"], "end": round(e, 2), "text": l["text"]} for l, e in zip(lines, ends)],
                           "estimated": bool(est), "total": end}, indent=2, ensure_ascii=False)
    if fmt in ("srt", "vtt"):
        out = ["WEBVTT", ""] if fmt == "vtt" else []
        for i, (l, e) in enumerate(zip(lines, ends), 1):
            if fmt == "srt":
                out.append(str(i))
            out += ["%s --> %s" % (_clock(l["t"], fmt == "srt"), _clock(e, fmt == "srt")), l["text"], ""]
        return "\n".join(out)
    return "\n".join("%s  %s" % (_stamp(l["t"]), l["text"]) for l in lines) + "\n"


def script_save(body):
    fmt = body.get("fmt") if body.get("fmt") in ("txt", "srt", "vtt", "json") else "txt"
    lines = body.get("lines")
    if not isinstance(lines, list) or not lines:
        return {"error": "There is no script to save."}, 400
    try:
        text = script_text(lines, fmt, body.get("end", 0), body.get("estimated", True))
    except (KeyError, TypeError, ValueError):
        return {"error": "The script is not valid."}, 400
    folder = Path(str(body.get("out_dir") or default_output_dir()))
    folder.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^\w\-]", "_", str(body.get("scene") or "scene"))[:60]
    out = folder / f"{name}_script.{fmt}"
    out.write_text(text, encoding="utf-8-sig" if fmt in ("srt", "vtt") else "utf-8")
    return {"path": str(out), "name": out.name, "folder": str(folder)}, 200


def pick_media():
    """Choose a video, audio or image file and copy it into the open project (assets/)."""
    if not project.current():
        return {"error": "Open or create a project first."}, 409
    script = (
        "import tkinter as tk\nfrom tkinter import filedialog\n"
        "r = tk.Tk(); r.withdraw(); r.attributes(\"-topmost\", True)\n"
        "p = filedialog.askopenfilename(title=\"Add a file to the project\", filetypes=[(\"Video, audio and images\", \"*.mp4 *.mov *.mkv *.webm *.wav *.mp3 *.m4a *.ogg *.png *.jpg *.jpeg\")])\n"
        "print(p or \"\")\n"
    )
    try:
        out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, creationflags=NO_WINDOW, timeout=300).stdout.strip()
    except Exception:
        out = ""
    if not out:
        return {"cancelled": True}, 200
    try:
        return project.import_file(out), 200
    except (ValueError, OSError) as exc:
        return {"error": str(exc)}, 400


def report_save(body):
    """Write a problem report to Documents/Manimo/reports so the user can send it. Nothing is sent from here."""
    text = str(body.get("text", ""))[:400_000]
    docs = Path.home() / "Documents"
    folder = (docs if docs.is_dir() else Path.home()) / "Manimo" / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    name = time.strftime("manimo-report-%Y%m%d-%H%M%S.txt")
    (folder / name).write_text(text, encoding="utf-8")
    return {"name": name, "path": str(folder / name), "folder": str(folder)}, 200


def open_mail(body):
    """Open the user's email app with a problem report addressed to the author. Only this one address is ever used."""
    from urllib.parse import quote
    subject = str(body.get("subject") or "Manimo problem report")[:140]
    text = str(body.get("body") or "")[:1900]
    url = "mailto:mathannits92@gmail.com?subject=" + quote(subject) + "&body=" + quote(text)
    if os.name == "nt":
        os.startfile(url)  # noqa: S606 - hands a mailto: link to the user's default mail app
    else:
        webbrowser.open(url)
    return {"ok": True}, 200


def voice_preview(body):
    if not voice.available():
        return {"error": "The narration voice is not installed. Reinstall Manimo to add it."}, 409
    text = " ".join(str(body.get("text") or "").split())[:400] or "Here is how this voice sounds, reading your narration."
    try:
        path = voice.speak(text, body.get("voice"), body.get("speed"))
    except Exception as exc:   # a broken model file or missing runtime should say so, not hang the page
        return {"error": "Could not make the voice: %s" % exc}, 500
    return {"url": f"/files/{serve_dir(path.parent)}/{path.name}"}, 200


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def save_recording(url, stream, length):
    """Receive a browser recording (voice, or voice + camera) and lay it over a rendered video with ffmpeg.
    The animation is not re-rendered: with voice only the picture is copied untouched."""
    from urllib.parse import urlparse, parse_qs
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    src = Path(q.get("path", ""))
    if not src.is_file() or src.suffix.lower() not in (".mp4", ".mov", ".webm", ".mkv"):
        return {"error": "Pick a rendered video first."}, 400
    if length <= 0 or length > 800_000_000:
        return {"error": "The recording is empty or too large."}, 413
    ff = ffmpeg_exe()
    if not ff:
        return {"error": "The video tool (ffmpeg) is missing. Reinstall Manimo to add it."}, 500
    cam = q.get("cam") == "1"
    try:
        dur = max(0.5, min(float(q.get("dur", "0")), 36000)) or None
    except ValueError:
        dur = None
    tmp = Path(tempfile.mkdtemp(prefix="manimo-rec-"))
    try:
        rec = tmp / "rec.webm"
        with open(rec, "wb") as f:
            left = length
            while left > 0:
                chunk = stream.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        out = src.with_name(src.stem + "_narrated.mp4")
        n = 2
        while out.exists():
            out = src.with_name(f"{src.stem}_narrated_{n}.mp4"); n += 1
        cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-i", str(rec)]
        if cam:
            cmd += ["-filter_complex", "[1:v]scale=360:-2[c];[0:v][c]overlay=W-w-24:H-h-24[v]", "-map", "[v]", "-map", "1:a?",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
        else:
            cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy"]
        cmd += ["-c:a", "aac", "-b:a", "160k", "-af", "apad"]
        if dur:
            cmd += ["-t", "%.3f" % dur]
        cmd += ["-movflags", "+faststart", str(out)]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1200, creationflags=0x08000000 if os.name == "nt" else 0)
        if p.returncode != 0 or not out.exists():
            return {"error": "Could not combine the recording: " + (p.stderr or "")[-300:]}, 500
        return file_entry(out, "video"), 200
    except subprocess.TimeoutExpired:
        return {"error": "Combining the recording took too long."}, 500
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def find_running_instance():
    for port in range(FIRST_PORT, FIRST_PORT + PORT_SPAN):
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=0.6) as r:
                if json.load(r).get("app") == "manimgx":
                    return port
        except Exception:
            continue
    return None


class LocalServer(ThreadingHTTPServer):
    """On Windows, SO_REUSEADDR lets a second server bind a port that is already in use (the old one
    keeps answering), so the window could open some other local site. Take the port exclusively instead."""
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server():
    for port in range(FIRST_PORT, FIRST_PORT + PORT_SPAN):
        try:
            return LocalServer(("127.0.0.1", port), Handler)
        except OSError:
            continue
    return None


def stop_running_job():
    with _lock:
        running = _job.get("state") == "running"
        if running:
            _job["state"] = "cancelled"
    if running and _proc is not None:
        kill_tree(_proc)


def open_window(url):
    """Fallback shell: a chromeless Edge/Chrome app window (used when the native window is unavailable)."""
    if os.name == "nt":
        roots = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LocalAppData")]
        rels = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"]
        for rel in rels:
            for root in filter(None, roots):
                exe = Path(root) / rel
                if exe.exists():
                    subprocess.Popen([str(exe), f"--app={url}"], creationflags=NO_WINDOW)
                    return
    webbrowser.open(url)


def watchdog(server):
    while True:
        time.sleep(10)
        with _lock:
            busy = _job.get("state") == "running"
        if _pinged and not busy and time.time() - _last_ping > IDLE_EXIT_SECONDS:
            server.shutdown()
            return


project.configure(find_scenes=find_scenes, file_entry=file_entry, ffmpeg_exe=ffmpeg_exe, speak=voice.speak, voice_available=voice.available)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-window", action="store_true", help="do not open any window")
    args = ap.parse_args()

    existing = find_running_instance()
    if existing:
        if not args.no_window:
            open_window(f"http://127.0.0.1:{existing}/")
        return
    server = create_server()
    if server is None:
        sys.exit("Manimo could not find a free local port.")
    threading.Thread(target=watchdog, args=(server,), daemon=True).start()
    if not args.no_window:
        threading.Timer(0.4, open_window, args=(f"http://127.0.0.1:{server.server_address[1]}/",)).start()
    try:
        server.serve_forever()
    finally:
        stop_running_job()


if __name__ == "__main__":
    main()
