"""Manimo projects: one folder per lesson, opened through its project.mo file.

    MyLesson/
        project.mo        settings, which renders belong to which scene, the timeline
        scenes/           one .py file per part of the lesson
        renders/          the videos (and subtitles) made from the scenes
        recordings/       your voice and camera recordings
        assets/           music, logos, anything you import
        exports/          the finished lesson videos

project.mo is plain JSON with a format number. Every path inside it is relative to the project folder, so the folder
can be moved, zipped or copied to another PC. Keys and other secrets are never stored in a project.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

MANIFEST = "project.mo"
FORMAT = 1
SUBDIRS = ("scenes", "renders", "recordings", "assets", "exports")
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Manimo" / "data"
RECENT_FILE = DATA_DIR / "recent-projects.json"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
MEDIA_TYPES = {".mp4", ".mov", ".webm", ".mkv", ".wav", ".mp3", ".m4a", ".ogg", ".png", ".jpg", ".jpeg", ".srt"}
AUDIO_TYPES = {".wav", ".mp3", ".m4a", ".ogg", ".webm"}
STARTER = '''import manimgx as m


class Intro(m.Scene):
    def construct(self) -> None:
        title = m.Text("My lesson", font_size=48)
        self.play(m.Write(title))
        self.wait(1)
'''
PRESETS = {   # name: (width, height, crf, fps, x264 preset)
    "high": (1920, 1080, 18, 30, "veryfast"),
    "small": (1280, 720, 27, 30, "veryfast"),
    "draft": (854, 480, 28, 30, "ultrafast"),
    "share": (1280, 720, 31, 30, "veryfast"),        # small enough for a chat message
}
SHAPES = {"16:9": (16, 9), "9:16": (9, 16), "1:1": (1, 1), "4:3": (4, 3), "3:4": (3, 4)}

_lock = threading.RLock()
_cur = None
_deps = {}
_probe_cache = {}
_export = {"state": "idle"}


def configure(**kw):
    _deps.update(kw)


# ---------------------------------------------------------------- basics
def safe_name(text, fallback="Untitled"):
    return re.sub(r"[^\w\- ]", "", str(text or "")).strip()[:60] or fallback


def current():
    return _cur


def renders_dir():
    return _cur / "renders" if _cur else None


def _inside(rel):
    """A path inside the project, or None if `rel` tries to leave it."""
    if not _cur:
        return None
    p = (_cur / str(rel)).resolve()
    try:
        p.relative_to(_cur.resolve())
    except ValueError:
        return None
    return p


def _read(folder):
    return json.loads((Path(folder) / MANIFEST).read_text(encoding="utf-8-sig"))      # tolerate a BOM added by another editor


def _write(folder, data):
    tmp = Path(folder) / (MANIFEST + ".part")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, Path(folder) / MANIFEST)


def _manifest():
    return _read(_cur)


def _recent():
    try:
        return [p for p in json.loads(RECENT_FILE.read_text(encoding="utf-8")) if (Path(p) / MANIFEST).is_file()][:8]
    except Exception:
        return []


def _remember(folder):
    items = [str(folder)] + [p for p in _recent() if p != str(folder)]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RECENT_FILE.write_text(json.dumps(items[:8]), encoding="utf-8")


def default_parent():
    docs = Path.home() / "Documents"
    return (docs if docs.is_dir() else Path.home()) / "Manimo Projects"


# ---------------------------------------------------------------- new / open / close
def new(name, parent=None, starter=True, remember=True):
    global _cur
    name = safe_name(name, "My lesson")
    base = Path(parent) if parent else default_parent()
    base.mkdir(parents=True, exist_ok=True)
    folder, n = base / name, 2
    while folder.exists():
        folder = base / f"{name} {n}"
        n += 1
    folder.mkdir()
    for d in SUBDIRS:
        (folder / d).mkdir()
    if starter:
        (folder / "scenes" / "intro.py").write_text(STARTER, encoding="utf-8")
    _write(folder, {"format": FORMAT, "name": name, "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "settings": {}, "renders": {},
                    "timeline": {"clips": [], "audio": [], "size": "auto", "fps": 30}})
    with _lock:
        _cur = folder
    if remember:
        _remember(folder)
    return state()


def edit_video(src):
    """Get one finished video ready for Compose. With a project open, the video joins it (a file already inside is
    used where it is); with none, a small hidden-from-Recent project in Documents\\Manimo Projects\\Quick edits holds it."""
    s = Path(str(src))
    if not s.is_file() or s.suffix.lower() not in MEDIA_TYPES - {".srt"}:
        raise ValueError("That video could not be found. Render it again, then try Edit video.")
    quick = _cur is None
    if quick:
        folder = default_parent() / "Quick edits" / safe_name("Edit " + s.stem, "Edit video")
        if (folder / MANIFEST).is_file():
            open_project(folder, remember=False)
        else:
            new(folder.name, folder.parent, starter=False, remember=False)
    try:
        rel = s.resolve().relative_to(_cur.resolve()).as_posix()
    except ValueError:
        same = _cur / "assets" / s.name
        rel = f"assets/{s.name}" if same.is_file() and same.stat().st_size == s.stat().st_size else import_file(s)["src"]
    st = state()
    st.update(src=rel, quick=quick)
    return st


def open_project(path, remember=True):
    global _cur
    p = Path(str(path))
    folder = p.parent if p.name.lower() == MANIFEST or p.suffix.lower() == ".mo" else p
    if not (folder / MANIFEST).is_file():
        raise ValueError("That folder is not a Manimo project (it has no project.mo).")
    data = _read(folder)
    if int(data.get("format", 1)) > FORMAT:
        raise ValueError("This project was made by a newer version of Manimo. Update Manimo to open it.")
    for d in SUBDIRS:
        (folder / d).mkdir(exist_ok=True)
    with _lock:
        _cur = folder.resolve()
    if remember:
        _remember(_cur)
    return state()


def close():
    global _cur
    with _lock:
        _cur = None
    return {"open": False, "recent": _recent(), "default_parent": str(default_parent())}


# ---------------------------------------------------------------- scenes
def scene_hash(code, scene, s):
    speaks = bool(re.search(r"\.(say|voiceover)\(", code))
    parts = [code, scene, str(s.get("quality")), str(s.get("fps")), str(s.get("encoding"))]
    if s.get("shape") not in (None, "auto"):          # only a chosen shape counts, so older projects stay up to date
        parts.append(str(s["shape"]))
    if speaks:
        try:
            speed = "%.2f" % float(s.get("speed"))      # 1, 1.0 and "1" are the same speed
        except (TypeError, ValueError):
            speed = str(s.get("speed"))
        parts += [str(s.get("voice")), speed]
    return hashlib.sha1("\x00".join(parts).encode("utf-8")).hexdigest()[:16]


def _scene_files():
    return sorted((_cur / "scenes").glob("*.py"), key=lambda p: p.name.lower())


def scene_items(s):
    man, items = _manifest(), []
    for f in _scene_files():
        code = f.read_text(encoding="utf-8-sig", errors="replace")      # a BOM from another editor is not part of the code
        names = _deps["find_scenes"](code)
        if not names:
            items.append({"file": f.name, "scene": None, "status": "none", "seconds": None})
            continue
        for sc in names:
            rec = man.get("renders", {}).get(f"{f.name}::{sc}")
            status, secs = "none", None
            if rec and (_cur / rec["path"]).is_file():
                status = "ok" if rec.get("hash") == scene_hash(code, sc, s) else "stale"
                secs = rec.get("video_seconds")
            items.append({"file": f.name, "scene": sc, "status": status, "seconds": secs, "render": rec["path"] if rec and status != "none" else None})
    return items


def _media():
    out = {}
    for d in ("renders", "recordings", "assets", "exports"):
        for f in sorted((_cur / d).glob("*")):
            if f.is_file() and f.suffix.lower() in MEDIA_TYPES:
                e = _deps["file_entry"](f, "media")
                kind = "image" if f.suffix.lower() in (".png", ".jpg", ".jpeg") else "video"
                if f.suffix.lower() in AUDIO_TYPES and d != "renders":
                    kind = "audio"
                    if f.suffix.lower() == ".webm":      # a webm may be a camera recording: look inside
                        try:
                            kind = "video" if probe(f"{d}/{f.name}")["video"] else "audio"
                        except (ValueError, OSError):
                            pass
                out[f"{d}/{f.name}"] = {"url": e["url"], "size": e["size"], "type": kind}
    return out


def state(settings=None):
    if not _cur:
        return {"open": False, "recent": _recent(), "default_parent": str(default_parent())}
    s = settings or _manifest().get("settings", {})
    man = _manifest()
    return {"open": True, "name": man.get("name", _cur.name), "path": str(_cur), "scenes": scene_items(s), "timeline": man.get("timeline", {}),
            "media": _media(), "settings": man.get("settings", {}), "recent": _recent(), "files": [f.name for f in _scene_files()]}


def read_scene(file):
    p = _inside(f"scenes/{Path(str(file)).name}")
    if not p or not p.is_file():
        raise ValueError("That scene file is not in the project.")
    return {"file": p.name, "code": p.read_text(encoding="utf-8-sig", errors="replace")}


def write_scene(file, code):
    name = Path(str(file)).name
    if not name.lower().endswith(".py"):
        raise ValueError("Scene files end in .py")
    p = _inside(f"scenes/{name}")
    if not p:
        raise ValueError("That scene file is not in the project.")
    if len(code) > 1_500_000:
        raise ValueError("That file is too large to be a scene.")
    tmp = p.with_suffix(".py.part")
    tmp.write_text(code, encoding="utf-8")
    os.replace(tmp, p)
    return {"file": name}


def new_scene(name, code=None):
    stem = safe_name(name, "scene").replace(" ", "_").lower()
    p, n = _cur / "scenes" / f"{stem}.py", 2
    while p.exists():
        p = _cur / "scenes" / f"{stem}_{n}.py"
        n += 1
    cls = "".join(w.capitalize() for w in re.split(r"[_\s]+", p.stem) if w) or "Scene1"
    if not cls[0].isalpha():
        cls = "Part" + cls
    p.write_text(code if code is not None else STARTER.replace("Intro", cls).replace("My lesson", cls), encoding="utf-8")
    return {"file": p.name}


def delete_scene(file):
    p = _inside(f"scenes/{Path(str(file)).name}")
    if not p or not p.is_file():
        raise ValueError("That scene file is not in the project.")
    trash = _cur / ".trash"
    trash.mkdir(exist_ok=True)
    os.replace(p, trash / f"{int(time.time())}-{p.name}")      # recoverable: nothing is permanently deleted
    man = _manifest()
    man["renders"] = {k: v for k, v in man.get("renders", {}).items() if not k.startswith(p.name + "::")}
    _write(_cur, man)
    return {"ok": True}


def rename_scene(file, new_name):
    old = _inside(f"scenes/{Path(str(file)).name}")
    stem = safe_name(Path(str(new_name)).stem, "scene").replace(" ", "_").lower()
    new = _inside(f"scenes/{stem}.py")
    if not old or not old.is_file() or not new:
        raise ValueError("That scene file is not in the project.")
    if new.exists():
        raise ValueError("A scene with that name already exists.")
    os.replace(old, new)
    man = _manifest()
    man["renders"] = {(new.name + k[len(old.name):] if k.startswith(old.name + "::") else k): v for k, v in man.get("renders", {}).items()}
    _write(_cur, man)
    return {"file": new.name}


def record_render(file, scene, digest, dest, video_seconds):
    if not _cur:
        return
    with _lock:
        man = _manifest()
        man.setdefault("renders", {})[f"{file}::{scene}"] = {"path": str(Path(dest).resolve().relative_to(_cur.resolve())).replace("\\", "/"), "hash": digest,
                                                             "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "video_seconds": video_seconds}
        _write(_cur, man)


def set_settings(s):
    keep = {k: s[k] for k in ("voice", "speed", "quality", "fps", "encoding", "shape") if k in s}
    with _lock:
        man = _manifest()
        man["settings"] = keep
        _write(_cur, man)
    return {"ok": True}


# ---------------------------------------------------------------- media and timeline
def probe(rel):
    p = _inside(rel)
    if not p or not p.is_file():
        raise ValueError("That file is not in the project.")
    key = (str(p), p.stat().st_mtime_ns)
    if key in _probe_cache:
        return dict(_probe_cache[key])
    ff = _deps["ffmpeg_exe"]()
    if not ff:
        raise ValueError("The video tool (ffmpeg) is missing. Reinstall Manimo.")
    r = subprocess.run([ff, "-hide_banner", "-i", str(p)], capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
    text = r.stderr or ""
    d = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0.0
    size = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", text)
    fps = re.search(r"(\d+(?:\.\d+)?)\s*fps", text)
    if dur <= 0 and re.search(r"(Audio|Video):", text):      # browser recordings have no length in their header: read the whole file once
        r2 = subprocess.run([ff, "-hide_banner", "-i", str(p), "-f", "null", "-"], capture_output=True, text=True, timeout=300, creationflags=NO_WINDOW)
        tm = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", r2.stderr or "")
        if tm:
            h_, m_, s_ = tm[-1]
            dur = int(h_) * 3600 + int(m_) * 60 + float(s_)
    info = {"duration": round(dur, 3), "audio": bool(re.search(r"Audio:", text)), "video": bool(re.search(r"Video:", text)),
            "width": int(size.group(1)) if size else None, "height": int(size.group(2)) if size else None, "fps": float(fps.group(1)) if fps else None}
    _probe_cache[key] = info
    return dict(info)


def set_timeline(tl):
    clips, audio = [], []
    for c in (tl.get("clips") or [])[:300]:
        if _inside(c.get("src", "")) is None:
            continue
        out = c.get("out")
        clips.append({"id": str(c.get("id") or ""), "src": str(c["src"]), "label": str(c.get("label") or "")[:80],
                      "in": max(0.0, float(c.get("in") or 0)), "out": None if out in (None, "") else max(0.0, float(out)), "fade": bool(c.get("fade"))})
    for a in (tl.get("audio") or [])[:100]:
        if _inside(a.get("src", "")) is None:
            continue
        audio.append({"id": str(a.get("id") or ""), "src": str(a["src"]), "label": str(a.get("label") or "")[:80],
                      "start": max(0.0, float(a.get("start") or 0)), "volume": min(2.0, max(0.0, float(a.get("volume", 1)))),
                      "in": max(0.0, float(a.get("in") or 0)), "kind": "music" if a.get("kind") == "music" else "voice", "loop": bool(a.get("loop"))})
    cams = []
    for k in (tl.get("cams") or [])[:20]:
        if _inside(k.get("src", "")) is None:
            continue
        cams.append({"id": str(k.get("id") or ""), "src": str(k["src"]), "label": str(k.get("label") or "")[:80], "start": max(0.0, float(k.get("start") or 0)),
                     "in": max(0.0, float(k.get("in") or 0)), "corner": k.get("corner") if k.get("corner") in ("br", "bl", "tr", "tl") else "br",
                     "size": min(60, max(10, int(k.get("size") or 28))), "volume": min(2.0, max(0.0, float(k.get("volume", 1))))})
    size = str(tl.get("size") or "auto")          # the video's shape: "auto" (the first clip's), or 16:9, 9:16, 1:1, 4:3, 3:4
    if size not in SHAPES:
        size = "auto"
    with _lock:
        man = _manifest()
        man["timeline"] = {"clips": clips, "audio": audio, "cams": cams, "size": size, "fps": 60 if tl.get("fps") == 60 else 30}
        _write(_cur, man)
    return {"ok": True}


def save_upload(name, stream, length, folder="recordings", convert=None):
    if not _cur:
        raise ValueError("Open a project first.")
    if length <= 0 or length > 800_000_000:
        raise ValueError("The recording is empty or too large.")
    stem = safe_name(Path(str(name or "recording")).stem, "recording").replace(" ", "_")
    ext = Path(str(name or "")).suffix.lower()
    if ext not in AUDIO_TYPES | {".mp4", ".mov", ".mkv"}:
        ext = ".webm"
    p, n = _cur / folder / f"{stem}{ext}", 2
    while p.exists():
        p = _cur / folder / f"{stem}_{n}{ext}"
        n += 1
    left = length
    with open(p, "wb") as f:
        while left > 0:
            chunk = stream.read(min(1 << 20, left))
            if not chunk:
                break
            f.write(chunk)
            left -= len(chunk)
    ff = _deps["ffmpeg_exe"]() if convert in ("audio", "video") else None
    if ff:      # browser recordings (webm) become m4a / mp4: they play everywhere and carry their length
        out = p.with_suffix(".m4a" if convert == "audio" else ".mp4")
        n = 2
        while out.exists():
            out = p.with_name(f"{p.stem}_{n}{out.suffix}")
            n += 1
        cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(p)]
        cmd += ["-vn", "-c:a", "aac", "-b:a", "160k"] if convert == "audio" else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                                                                                   "-vf", "scale=-2:min(720\\,ih)", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
        r = subprocess.run(cmd + [str(out)], capture_output=True, text=True, timeout=900, creationflags=NO_WINDOW)
        if r.returncode == 0 and out.is_file():
            p.unlink(missing_ok=True)
            p = out
    return {"src": f"{folder}/{p.name}"}


def import_file(src):
    s = Path(str(src))
    if not s.is_file() or s.suffix.lower() not in MEDIA_TYPES - {".srt"}:
        raise ValueError("Pick a video, audio or image file.")
    dest, n = _cur / "assets" / s.name, 2
    while dest.exists():
        dest = _cur / "assets" / f"{s.stem}_{n}{s.suffix}"
        n += 1
    shutil.copy2(s, dest)
    return {"src": f"assets/{dest.name}"}


def narrate_text(text, voice_id=None, speed=None):
    """Turn typed words into a voice-over file inside the project (the offline Kokoro voice)."""
    if not _deps.get("voice_available") or not _deps["voice_available"]():
        raise ValueError("The narration voice is not installed. Reinstall Manimo to add it.")
    text = " ".join(str(text or "").split())[:900]
    if not text:
        raise ValueError("Type the words to speak first.")
    wav = Path(_deps["speak"](text, voice_id, speed))
    dest = _cur / "recordings" / f"narration-{time.strftime('%H%M%S')}.wav"
    shutil.copy2(wav, dest)
    return {"src": f"recordings/{dest.name}"}


def save_cover(src, at):
    """One frame of a clip, saved next to the exports as a cover picture (JPEG)."""
    p = _inside(src)
    ff = _deps["ffmpeg_exe"]()
    if not p or not p.is_file() or not ff:
        raise ValueError("That clip could not be found.")
    out_dir = _cur / "exports"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"cover_{time.strftime('%Y%m%d-%H%M%S')}.jpg"
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{max(0.0, float(at)):.3f}", "-i", str(p), "-frames:v", "1", "-q:v", "2", str(out)],
                       capture_output=True, text=True, creationflags=NO_WINDOW, timeout=60)
    if not out.is_file():
        raise ValueError("Could not save the picture: " + (r.stderr or "")[-200:])
    return {"name": out.name, "folder": str(out_dir)}


# ---------------------------------------------------------------- chapters and subtitles
def _stamp(t):
    t = max(0, int(t))
    return f"{t // 60:02d}:{t % 60:02d}" if t < 3600 else f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def _srt_cues(path):
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        for i, l in enumerate(lines):
            m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", l.strip())
            if m:
                g = list(map(int, m.groups()))
                cues.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000, " ".join(lines[i + 1:])))
                break
    return cues


def _fmt_srt(t):
    ms = int(round(max(0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def clip_lengths(tl):
    out = []
    for c in tl["clips"]:
        info = probe(c["src"])
        end = c["out"] if c["out"] else info["duration"]
        end = min(end, info["duration"]) if info["duration"] else end
        out.append(max(0.1, end - c["in"]))
    return out


def chapters_and_subs(tl, lengths):
    chapters, cues, t = [], [], 0.0
    for c, ln in zip(tl["clips"], lengths):
        chapters.append(f"{_stamp(t)} {c['label'] or Path(c['src']).stem}")
        srt = (_inside(c["src"]) or Path("")).with_suffix(".srt")
        if srt.is_file():
            for a, b, txt in _srt_cues(srt):
                if b <= c["in"] or a >= c["in"] + ln:
                    continue
                cues.append((t + max(0, a - c["in"]), t + min(ln, b - c["in"]), txt))
        t += ln
    return chapters, cues


# ---------------------------------------------------------------- export
def export_state():
    with _lock:
        return dict(_export)


def start_export(preset, captions=False):
    if not _cur:
        raise ValueError("Open a project first.")
    with _lock:
        if _export.get("state") == "running":
            raise ValueError("An export is already running.")
    tl = _manifest().get("timeline", {})
    if not tl.get("clips"):
        raise ValueError("Add at least one clip to the timeline first.")
    preset = preset if preset in PRESETS or preset == "audio" else "high"
    with _lock:
        _export.clear()
        _export.update({"state": "running", "percent": 0.0, "preset": preset, "error": None, "started": time.time()})
    threading.Thread(target=_run_export, args=(tl, preset, bool(captions)), daemon=True).start()
    return {"ok": True}


def _fail(msg):
    with _lock:
        _export.update({"state": "error", "error": msg})


def _run_export(tl, preset, captions=False):
    try:
        ff = _deps["ffmpeg_exe"]()
        if not ff:
            return _fail("The video tool (ffmpeg) is missing. Reinstall Manimo.")
        lengths = clip_lengths(tl)
        total = sum(lengths)
        w, h, crf, fps, x264 = PRESETS.get(preset, PRESETS["high"])
        shape = tl.get("size") if tl.get("size") in SHAPES else None
        if shape is None and tl.get("clips"):                                 # auto: the shape of the first clip
            first = probe(tl["clips"][0]["src"])
            if first.get("width") and first.get("height"):
                shape = (first["width"], first["height"])
        a, b = SHAPES[shape] if isinstance(shape, str) else (shape or (16, 9))
        short = min(w, h)
        w, h = (int(round(short * a / b / 2) * 2), short) if a >= b else (short, int(round(short * b / a / 2) * 2))
        if tl.get("fps") == 60 and preset == "high":
            fps = 60
        cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats"]
        graph, labels = [], []
        FADE = 0.4
        for i, (c, ln) in enumerate(zip(tl["clips"], lengths)):
            info = probe(c["src"])
            cmd += ["-i", str(_inside(c["src"]))]
            vf = (f"[{i}:v]fps={fps},trim=start={c['in']:.3f}:duration={ln:.3f},setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=decrease,"      # fps first: ManimGX videos skip frames while nothing moves
                  f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p")
            if c.get("fade") and ln > 2 * FADE:
                vf += f",fade=t=in:st=0:d={FADE},fade=t=out:st={ln - FADE:.3f}:d={FADE}"
            graph.append(vf + f"[v{i}]")
            if info["audio"]:
                af = (f"[{i}:a]atrim=start={c['in']:.3f}:duration={ln:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                      f"aformat=sample_fmts=fltp:channel_layouts=stereo,apad=whole_dur={ln:.3f}")
                if c.get("fade") and ln > 2 * FADE:
                    af += f",afade=t=in:st=0:d={FADE},afade=t=out:st={ln - FADE:.3f}:d={FADE}"
                graph.append(af + f"[a{i}]")
            else:
                graph.append(f"anullsrc=r=48000:cl=stereo:d={ln:.3f},asetpts=PTS-STARTPTS[a{i}]")
            labels.append(f"[v{i}][a{i}]")
        n = len(tl["clips"])
        graph.append("".join(labels) + f"concat=n={n}:v=1:a=1[vc][ac]")
        extra, k, vlabel = [], n, "vc"
        for j, cam in enumerate(tl.get("cams", [])):                      # camera: a small picture in a corner, for as long as it runs
            p = _inside(cam["src"])
            if not p or not p.is_file():
                continue
            ci = probe(cam["src"])
            d = min(max(0.2, ci["duration"] - cam["in"]), max(0.2, total - cam["start"]))
            cmd += ["-i", str(p)]
            cw = max(64, int(w * cam["size"] / 100) // 2 * 2)
            pad = int(w * 0.02)
            x = f"{pad}" if cam["corner"] in ("bl", "tl") else f"W-w-{pad}"
            y = f"{pad}" if cam["corner"] in ("tl", "tr") else f"H-h-{pad}"
            graph.append(f"[{k}:v]fps={fps},trim=start={cam['in']:.3f}:duration={d:.3f},setpts=PTS-STARTPTS+{cam['start']:.3f}/TB,scale={cw}:-2,setsar=1,format=yuv420p[cv{j}]")
            graph.append(f"[{vlabel}][cv{j}]overlay=x={x}:y={y}:enable='between(t,{cam['start']:.3f},{cam['start'] + d:.3f})':eof_action=pass[vo{j}]")
            vlabel = f"vo{j}"
            if ci["audio"]:
                ms = int(cam["start"] * 1000)
                graph.append(f"[{k}:a]atrim=start={cam['in']:.3f}:duration={d:.3f},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                             f"volume={cam['volume']:.2f},adelay={ms}|{ms}[x{k}]")
                extra.append(f"[x{k}]")
            k += 1
        for a in tl.get("audio", []):
            p = _inside(a["src"])
            if not p or not p.is_file() or not probe(a["src"])["audio"]:
                continue
            ai = probe(a["src"])
            cmd += ["-i", str(p)]
            ms = int(a["start"] * 1000)
            base = f"[{k}:a]atrim=start={a.get('in', 0):.3f},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
            if a.get("kind") == "music" and a.get("loop") and ai["duration"] > 0.5:     # background music: repeat to fill the video, fade out at the end
                need = max(1.0, total - a["start"])
                size = int(ai["duration"] * 48000) + 48000
                base += (f",aloop=loop=-1:size={size},atrim=duration={need:.3f},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=1,"
                         f"afade=t=out:st={max(0.0, need - 1.5):.3f}:d=1.5")
            graph.append(base + f",volume={a['volume']:.2f},adelay={ms}|{ms}[x{k}]")
            extra.append(f"[x{k}]")
            k += 1
        burn = None
        if captions and preset != "audio":                                    # captions on the picture itself, from the scenes' subtitle files
            _, cues = chapters_and_subs(tl, lengths)
            if cues:
                burn = (_cur / "exports") / f".captions-{os.getpid()}.srt"
                burn.parent.mkdir(exist_ok=True)
                burn.write_text("".join(f"{i}\n{_fmt_srt(a)} --> {_fmt_srt(b)}\n{txt}\n\n" for i, (a, b, txt) in enumerate(cues, 1)), encoding="utf-8")
                fs = 14 if w >= h else 8                                       # ASS sizes and margins are in a 288-high space that scales with the video
                graph.append(f"[{vlabel}]subtitles=filename={burn.name}:force_style='FontName=Segoe UI,FontSize={fs},Outline=2,Shadow=0,MarginV=20,Alignment=2,PrimaryColour=&H00FFFFFF'[vcap]")
                vlabel = "vcap"
        if extra:
            graph.append("[ac]" + "".join(extra) + f"amix=inputs={1 + len(extra)}:duration=first:normalize=0[aout]")
            amap = "[aout]"
        else:
            amap = "[ac]"
        name = safe_name(_manifest().get("name", "lesson")).replace(" ", "_")
        out_dir = _cur / "exports"
        out_dir.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        if preset == "audio":
            out = out_dir / f"{name}_{stamp}.m4a"
            cmd += ["-filter_complex", ";".join(graph), "-map", amap, "-vn", "-c:a", "aac", "-b:a", "192k", str(out)]
        else:
            out = out_dir / f"{name}_{preset}_{stamp}.mp4"
            cmd += ["-filter_complex", ";".join(graph), "-map", f"[{vlabel}]", "-map", amap, "-c:v", "libx264", "-preset", x264, "-crf", str(crf),
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=NO_WINDOW, cwd=str(out_dir))
        errs = []
        threading.Thread(target=lambda: errs.append(proc.stderr.read()), daemon=True).start()
        for line in proc.stdout:
            m = re.match(r"out_time_(?:us|ms)=(\d+)", line.strip())
            if m and total:
                with _lock:
                    _export["percent"] = min(99.0, 100.0 * int(m.group(1)) / 1_000_000 / total)
        proc.wait()
        if burn is not None:
            burn.unlink(missing_ok=True)
        if proc.returncode != 0 or not out.exists():
            return _fail("Could not make the video: " + ((errs[0] if errs else "") or "unknown error")[-400:])
        chapters, cues = chapters_and_subs(tl, lengths)
        (out_dir / f"{out.stem}_chapters.txt").write_text("\n".join(chapters) + "\n", encoding="utf-8")
        if cues:
            (out_dir / f"{out.stem}.srt").write_text("\n".join(f"{i}\n{_fmt_srt(a)} --> {_fmt_srt(b)}\n{t}\n" for i, (a, b, t) in enumerate(cues, 1)), encoding="utf-8-sig")
        with _lock:
            _export.update({"state": "done", "percent": 100.0, "file": _deps["file_entry"](out, "video"), "seconds": round(total, 1),
                            "chapters": f"exports/{out.stem}_chapters.txt", "subtitles": f"exports/{out.stem}.srt" if cues else None})
    except Exception as exc:      # report anything unexpected in the app instead of failing silently
        _fail(f"Could not make the video: {exc}")


# ---------------------------------------------------------------- routes
def handle(method, path, body):
    """Routes used by server.py. Returns (payload, status)."""
    try:
        if method == "GET" and path == "/api/project":
            return state(), 200
        if method == "GET" and path == "/api/project/export":
            return export_state(), 200
        if path == "/api/project/new":
            return new(body.get("name"), body.get("parent")), 200
        if path == "/api/project/open":
            return open_project(body.get("path", "")), 200
        if path == "/api/project/state":
            return state(body.get("settings")), 200
        if path == "/api/project/close":
            return close(), 200
        if path == "/api/project/edit-video":
            return edit_video(body.get("path", "")), 200
        if not _cur:
            return {"error": "Open or create a project first."}, 409
        if path == "/api/project/scene-read":
            return read_scene(body.get("file")), 200
        if path == "/api/project/scene-write":
            return write_scene(body.get("file"), str(body.get("code", ""))), 200
        if path == "/api/project/scene-new":
            return new_scene(body.get("name"), body.get("code")), 200
        if path == "/api/project/scene-delete":
            return delete_scene(body.get("file")), 200
        if path == "/api/project/scene-rename":
            return rename_scene(body.get("file"), body.get("name")), 200
        if path == "/api/project/settings":
            return set_settings(body), 200
        if path == "/api/project/timeline":
            return set_timeline(body.get("timeline") or {}), 200
        if path == "/api/project/media-info":
            return probe(body.get("src", "")), 200
        if path == "/api/project/export":
            return start_export(body.get("preset"), body.get("captions")), 200
        if path == "/api/project/narrate":
            return narrate_text(body.get("text"), body.get("voice"), body.get("speed")), 200
        if path == "/api/project/cover":
            return save_cover(body.get("src", ""), body.get("at", 0)), 200
        if path == "/api/project/import":
            return import_file(body.get("path", "")), 200
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {"error": str(exc)}, 400
    return {"error": "not found"}, 404
