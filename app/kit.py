"""Teacher kit: a lesson handout (PDF) with the solved problem, the narration as steps and optional frames from the videos; a GIF of a scene;
a share folder (one video, a cover, title, description and chapters); and the teacher's brand (name, logo, colour) used on the handout.

The PDF is made by printing a styled HTML page with the Edge browser that Windows already has (headless), so equations, Greek letters and
any language print correctly and no extra library is needed. If Edge cannot be found the HTML handout is saved instead, to print from a browser."""
import base64
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import narration
import pptx_writer

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Manimo" / "data"
BRAND_FILE = DATA_DIR / "brand.json"
SITE = "https://mathanmj92.github.io/manimo-site/"
VIDEO_TYPES = {".mp4", ".mov", ".mkv", ".webm"}
MANIMO_TEAL = "#1fa5bd"
LABELS = ("Given", "Find", "Method", "Steps", "Answer", "Check")
_deps = {}
_lock = threading.Lock()
_job = {"state": "idle"}


def configure(**kw):
    _deps.update(kw)


# ---------------------------------------------------------------- the teacher's brand
DEFAULT_BRAND = {"name": "", "tagline": "", "accent": MANIMO_TEAL, "logo": ""}


def brand_get():
    try:
        data = json.loads(BRAND_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**DEFAULT_BRAND, **{k: v for k, v in data.items() if k in DEFAULT_BRAND and isinstance(v, str)}}
    except (OSError, ValueError):
        pass
    return dict(DEFAULT_BRAND)


def brand_set(body):
    b = brand_get()
    if "name" in body:
        b["name"] = " ".join(str(body["name"]).split())[:80]
    if "tagline" in body:
        b["tagline"] = " ".join(str(body["tagline"]).split())[:120]
    if "accent" in body:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(body["accent"])):
            return {"error": "The colour must look like #1fa5bd."}, 400
        b["accent"] = str(body["accent"]).lower()
    if "logo" in body:
        logo = str(body["logo"] or "")
        if logo and (not re.match(r"data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$", logo) or len(logo) > 600_000):
            return {"error": "The logo must be a PNG, JPEG or WebP picture under about 400 KB."}, 400
        b["logo"] = logo
    try:
        BRAND_FILE.parent.mkdir(parents=True, exist_ok=True)
        BRAND_FILE.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        return {"error": f"Could not save the brand: {exc}"}, 500
    return b, 200


# ---------------------------------------------------------------- the job (one export at a time)
def job():
    with _lock:
        return dict(_job)


def _set(**kw):
    with _lock:
        _job.update(kw)


def _start(kind, fn, body):
    with _lock:
        if _job.get("state") == "running":
            return {"error": "Another export is still running."}, 409
        _job.clear()
        _job.update({"state": "running", "kind": kind, "step": "Starting…", "percent": 0, "started": time.time()})

    def run():
        try:
            result = fn(body)
            _set(state="done", percent=100, step="Done", **result)
        except KitError as exc:
            _set(state="error", error=str(exc))
        except Exception as exc:                      # never leave the page waiting
            _set(state="error", error=f"The export stopped unexpectedly: {exc}")
    threading.Thread(target=run, daemon=True).start()
    return {"ok": True}, 200


class KitError(Exception):
    pass


# ---------------------------------------------------------------- frames and videos
def _ffmpeg():
    ff = _deps["ffmpeg"]()
    if not ff:
        raise KitError("The video tool (ffmpeg) is missing. Reinstall Manimo.")
    return ff


def video_ok(path):
    p = Path(str(path or ""))
    return p if p.is_file() and p.suffix.lower() in VIDEO_TYPES else None


def duration(ff, video):
    r = subprocess.run([ff, "-hide_banner", "-i", str(video)], capture_output=True, text=True, creationflags=NO_WINDOW, timeout=60)
    d = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr or "")
    return int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0.0


def frame(ff, video, t, width=960, light=False):
    """One frame of a video as JPEG bytes (None if it cannot be read). `light` swaps the dark background for a white one, keeping the colours, for printing."""
    tmp = Path(tempfile.mkdtemp(prefix="manimo-frame-"))
    try:
        out = tmp / "f.jpg"
        vf = f"scale={width}:-2" + (",negate,hue=h=180" if light else "")
        subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}", "-i", str(video), "-frames:v", "1", "-vf", vf, "-q:v", "3", str(out)],
                       capture_output=True, creationflags=NO_WINDOW, timeout=60)
        return out.read_bytes() if out.is_file() else None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


MIN_FRAME_BYTES = 4500          # a black or empty 960-pixel frame is about 2.5 KB as a JPEG; a frame with writing on it is far larger


def frame_windows(n_lines, length, timing):
    """The stretch of the video where each spoken line is on screen: from when it starts to just before the next one does. Without measured
    times the lines are spread evenly over the video."""
    if n_lines <= 0 or length <= 0:
        return []
    starts = [float(l["t"]) for l in (timing or {}).get("lines", [])]
    end = float((timing or {}).get("end") or length)
    if len(starts) == n_lines:
        edges = starts + [end]
    else:
        edges = [length * i / n_lines for i in range(n_lines + 1)]
    out = []
    for i in range(n_lines):
        lo, hi = edges[i], max(edges[i] + 0.4, edges[i + 1] - 0.1)
        out.append((round(min(lo, max(0.0, length - 0.2)), 2), round(min(hi, max(0.1, length - 0.1)), 2)))
    return out


def best_frame(ff, video, lo, hi, width=960, light=False, limit=None):
    """The picture that shows the step complete. The animation is usually finished near the end of a line, so the latest moment wins, unless a
    fade-out has made it emptier than an earlier one: a frame counts as complete when it holds at least 88% of the most that any moment in the
    stretch holds. The last frame of a video often cannot be read, so moments are kept inside it, and one that cannot be read is skipped.
    None when every moment is blank."""
    if limit:
        hi = min(hi, limit - 0.3)
        lo = min(lo, hi)
    span = max(0.0, hi - lo)
    times = [round(lo + span * k / 4, 2) for k in range(5)] if span > 0.8 else [round(hi, 2)]
    shots = []
    for t in times:
        data = frame(ff, video, t, width, False)                  # judged on the dark original: a blank frame stays small, one with writing is large
        if data:
            shots.append((t, len(data), data))
    if not shots or max(s[1] for s in shots) < MIN_FRAME_BYTES:
        return None
    top = max(s[1] for s in shots)
    t, _, dark = [s for s in shots if s[1] >= 0.88 * top][-1]       # the latest complete one
    return (frame(ff, video, t, width, True) or dark) if light else dark


# ---------------------------------------------------------------- the solution text
def parse_solution(text):
    """'Given: ... Find: ... Steps: ... Answer: ...' as [(label, text)]; text without those labels comes back as one unlabelled part."""
    text = (text or "").strip()
    if not text:
        return []
    pat = re.compile(r"^\s*\**(" + "|".join(LABELS) + r")\**\s*:\s*\**\s*", re.M | re.I)
    marks = list(pat.finditer(text))
    if not marks:
        return [("", text)]
    parts = []
    if text[:marks[0].start()].strip():
        parts.append(("", text[:marks[0].start()].strip()))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        parts.append((m.group(1).capitalize(), text[m.end():end].strip()))
    return parts


# ---------------------------------------------------------------- the handout
def _img(data):
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def _para(text):
    return "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in re.split(r"\n\s*\n", text.strip()) if p.strip())


def _steps(text):
    """A 'Steps:' part as an ordered list when it is numbered, otherwise as paragraphs."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) > 1 and all(re.match(r"\d+[.)]\s", l) for l in lines):
        return "<ol>" + "".join(f"<li>{html.escape(re.sub(r'^\d+[.)]\s*', '', l))}</li>" for l in lines) + "</ol>"
    return _para(text)


def _lum(hex_colour):
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b="#ffffff"):
    """The WCAG contrast ratio of two #rrggbb colours (4.5 or more is comfortable for normal text)."""
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def readable_accent(hex_colour, minimum=4.5):
    """The teacher's accent, darkened step by step until text in it can be read on white paper. The accent itself is still used for borders."""
    c = hex_colour
    for _ in range(40):
        if contrast(c) >= minimum:
            return c
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        c = "#%02x%02x%02x" % (int(r * 0.93), int(g * 0.93), int(b * 0.93))
    return "#1c2333"


def _darker(hex_colour, k=0.72):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (int(r * k), int(g * k), int(b * k))


def _css_text(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


CSS = """
@page { size: A4; margin: 15mm 14mm 20mm;
  @bottom-left { content: var(--footer-text); font: 8.5pt 'Segoe UI', sans-serif; color: #4d576b; vertical-align: top; padding-top: 4mm; }
  @bottom-right { content: counter(page); font: 9pt 'Segoe UI', sans-serif; color: #4d576b; vertical-align: top; padding-top: 4mm; } }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font: var(--base) / 1.55 'Segoe UI', system-ui, sans-serif; color: #1c2333; }
h1 { font-size: calc(var(--base) * 2); line-height: 1.2; margin: 0 0 4px; letter-spacing: -.01em; }
h2 { font-size: calc(var(--base) * 1.3); margin: 20px 0 8px; padding-bottom: 4px; border-bottom: 2px solid var(--accent); break-after: avoid; }
h3 { font-size: calc(var(--base) * 1.05); margin: 14px 0 4px; color: var(--accent-text); break-after: avoid; }
p { margin: 0 0 7px; }
.top { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid #dfe3ec; }
.top img { max-height: 44px; max-width: 120px; object-fit: contain; }
.top .who { font-weight: 600; } .top .tag { color: #4d576b; font-size: calc(var(--base) * .9); }
.meta { color: #4d576b; font-size: calc(var(--base) * .95); margin-bottom: 4px; }
.problem { border-left: 5px solid var(--accent); background: #f4f7fb; border-radius: 6px; padding: 10px 14px; margin: 12px 0; break-inside: avoid; }
.problem .label { font-weight: 700; font-size: calc(var(--base) * .88); letter-spacing: .04em; color: var(--accent-text); margin-bottom: 4px; }
.fig { margin: 10px 0; text-align: center; break-inside: avoid; }
.fig img { width: 100%; max-width: 150mm; margin: 0 auto; }
.fig img, .step img { border-radius: 6px; border: 1px solid #c9cfdc; background: #fff; display: block; }
.fig figcaption, .step figcaption { font-size: calc(var(--base) * .85); color: #4d576b; margin-top: 3px; }
.sol { margin: 8px 0; } .sol dt { font-weight: 700; color: var(--accent-text); margin-top: 8px; break-after: avoid; } .sol dd { margin: 2px 0 0; break-before: avoid; }
.sol ol { margin: 2px 0 6px 18px; padding: 0; } .sol li { margin-bottom: 3px; }
.answer { border: 2px solid var(--accent); border-radius: 8px; padding: 8px 12px; margin: 10px 0; font-weight: 600; break-inside: avoid; }
.step { margin: 10px 0 16px; break-inside: avoid; }
.step.side { display: grid; grid-template-columns: 56% 1fr; gap: 12px; align-items: start; }
.step.big img { width: 100%; }
.step .text { margin-top: 6px; } .step.side .text { margin-top: 0; }
.step .n { display: inline-grid; place-items: center; width: 1.45em; height: 1.45em; border-radius: 50%; background: var(--accent-text); color: #fff; font-size: calc(var(--base) * .85); font-weight: 700; margin-right: 6px; }
.empty { color: #4d576b; font-style: italic; }
"""


def lesson_html(d):
    """d: title, audience, date, problem, solution, figure (jpeg bytes or None), sections [{name, steps: [{text, frame, caption}]}], brand,
    size ('large': one picture across the page, or 'compact': picture beside its text), large_print (bigger type)."""
    b = d["brand"]
    accent = b.get("accent") or MANIMO_TEAL
    base = "13pt" if d.get("large_print") else "11pt"
    footer = ("Prepared by " + b["name"] + " · " if b.get("name") else "") + "Made with Manimo · " + SITE.replace("https://", "").rstrip("/")
    top = ""
    if b.get("logo") or b.get("name"):
        top = ('<div class="top">' + (f'<img src="{b["logo"]}" alt="">' if b.get("logo") else "") +
               f'<div><div class="who">{html.escape(b.get("name", ""))}</div><div class="tag">{html.escape(b.get("tagline", ""))}</div></div></div>')
    out = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(d["title"])}</title>',
           f'<style>:root{{--accent:{accent};--accent-text:{readable_accent(accent)};--base:{base};--footer-text:{_css_text(footer)}}}{CSS}</style></head><body>', top,
           f'<h1>{html.escape(d["title"])}</h1>']
    meta = " · ".join(x for x in (d.get("audience"), d.get("date")) if x)
    if meta:
        out.append(f'<div class="meta">{html.escape(meta)}</div>')
    if d.get("problem"):
        out.append(f'<div class="problem"><div class="label">PROBLEM</div>{_para(d["problem"])}</div>')
    if d.get("figure"):
        out.append(f'<figure class="fig"><img src="{_img(d["figure"])}" alt="Figure"><figcaption>Figure</figcaption></figure>')
    sol = parse_solution(d.get("solution"))
    if sol:
        out.append("<h2>Solution</h2>")
        rows = []
        for label, text in sol:
            if label == "Answer":
                rows.append(f'<div class="answer">Answer: {html.escape(" ".join(text.split()))}</div>')
            elif not label:
                rows.append(_para(text))
            else:
                rows.append(f"<dt>{label}</dt><dd>{_steps(text) if label == 'Steps' else _para(text)}</dd>")
        body = "".join(rows)
        out.append(f'<dl class="sol">{body}</dl>' if any(r.startswith("<dt>") for r in rows) else body)
    big = d.get("size", "large") != "compact"
    for s in d["sections"]:
        out.append(f'<h2>{html.escape(s["name"])}</h2>')
        if not s["steps"]:
            out.append('<p class="empty">This scene has no narration.</p>')
        for i, st in enumerate(s["steps"], 1):
            txt = f'<div class="text"><span class="n">{i}</span>{html.escape(st["text"])}</div>' if st.get("text") else ""
            if st.get("frame"):
                img = f'<figure style="margin:0"><img src="{_img(st["frame"])}" alt="Step {i}"><figcaption>{html.escape(st.get("caption", ""))}</figcaption></figure>'
                out.append(f'<div class="step {"big" if big else "side"}">{img}{txt}</div>')
            else:
                out.append(f'<div class="step">{txt}</div>')
    out.append("</body></html>")
    return "".join(out)


def find_edge():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LocalAppData")):
        if base:
            for rel in ("Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe"):
                p = Path(base) / rel
                if p.is_file():
                    return p
    return None


def html_to_pdf(html_path, pdf_path):
    edge = find_edge()
    if not edge:
        return False
    prof = Path(tempfile.mkdtemp(prefix="manimo-edge-"))           # its own profile, so a running Edge is not disturbed
    try:
        pdf_path.unlink(missing_ok=True)
        subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-first-run", "--no-pdf-header-footer", f"--user-data-dir={prof}",
                        f"--print-to-pdf={pdf_path}", Path(html_path).resolve().as_uri()], capture_output=True, creationflags=NO_WINDOW, timeout=180)
    except (subprocess.TimeoutExpired, OSError):
        return False
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    return pdf_path.is_file() and pdf_path.stat().st_size > 1500


def _safe(name):
    return re.sub(r"[^\w\- ]+", "", str(name or "")).strip().replace(" ", "_")[:60] or "lesson"


def _out_dir(body):
    d = Path(str(body.get("out_dir") or ""))
    if not d.is_dir():
        raise KitError("The output folder could not be found.")
    return d


def _scene_video(out_dir, scene, given):
    v = video_ok(given)
    if v:
        return v
    return video_ok(out_dir / f"{scene}.mp4")


def collect_lesson(body):
    """Everything a handout or a slide deck needs: the title and text, the figure, and for every scene its steps (a spoken line and its picture)."""
    code = str(body.get("code") or "")[:400_000]
    out_dir = _out_dir(body)
    ff = _deps["ffmpeg"]()
    mode = body.get("frames") if body.get("frames") in ("lines", "few", "none") else "lines"
    light = body.get("light", True) is not False
    big = body.get("size", "large") != "compact"
    width = 1600 if big else 1100                                # pictures are printed or projected large: enough pixels to keep thin lines and small labels sharp
    try:
        lines = narration.public(code)
    except Exception as exc:
        raise KitError(str(exc)) from None
    given = {str(s.get("name")): s.get("video") for s in (body.get("scenes") or []) if isinstance(s, dict)}
    names = [str(s.get("name")) for s in (body.get("scenes") or []) if isinstance(s, dict)] or sorted({l["scene"] for l in lines}, key=lambda n: next(l["line"] for l in lines if l["scene"] == n))
    want = [n for n in names if not body.get("only") or n in body["only"]]
    sections, missing, blank, total = [], [], [], max(1, len(want))
    for k, name in enumerate(want):
        _set(step=f"Scene {k + 1} of {total}: {name}", percent=int(100 * k / total * 0.85))
        mine = [l for l in lines if l["scene"] == name]
        video = _scene_video(out_dir, name, given.get(name)) if mode != "none" and ff else None
        if mode != "none" and not video:
            missing.append(name)
        length = duration(ff, video) if video else 0.0
        frames = []
        if video and mode == "lines" and mine:
            timing = _deps["timing"](code, name, body.get("voice"), body.get("speed")) if _deps.get("timing") else None
            frames = [best_frame(ff, video, lo, hi, width, light, limit=length) for lo, hi in frame_windows(len(mine), length, timing)]
        elif video and (mode == "few" or (mode == "lines" and not mine)):
            n = min(6, max(1, int(body.get("per_scene") or 3)))
            frames = [best_frame(ff, video, a, b, width, light, limit=length) for a, b in frame_windows(n, length, None)]
        steps = []
        if mine and mode == "lines":
            for i, l in enumerate(mine):
                fr = frames[i] if i < len(frames) else None
                if video and not fr:
                    blank.append(f"{name}, step {i + 1}")
                steps.append({"text": re.sub(r"[\[\]]", "", l["text"]).strip(), "frame": fr})
        else:
            for text in (re.sub(r"[\[\]]", "", l["text"]).strip() for l in mine):
                steps.append({"text": text, "frame": None})
            for i, fr in enumerate(frames):
                if fr:
                    steps.append({"text": "", "frame": fr, "caption": f"{name}, {int(length * (i + 1) / len(frames))} s"})
        sections.append({"name": name, "steps": steps, "narration": " ".join(s["text"] for s in steps if s["text"])})
    figure = None
    if body.get("figure") and want and ff:
        v = _scene_video(out_dir, want[0], given.get(want[0]))
        if v:
            length = duration(ff, v)
            for a, b in ((0.55 * length, 0.92 * length), (0.25 * length, 0.55 * length), (0.1 * length, 0.25 * length)):      # the finished diagram, not the fade-out at the very end
                figure = best_frame(ff, v, a, b, 1600, light, limit=length)
                if figure:
                    break
    return {"title": " ".join(str(body.get("title") or "Lesson").split())[:120], "audience": " ".join(str(body.get("audience") or "").split())[:120],
            "date": time.strftime("%d %B %Y").lstrip("0"), "problem": str(body.get("problem") or "")[:6000], "solution": str(body.get("solution") or "")[:8000],
            "figure": figure, "sections": sections, "brand": brand_get(), "size": "large" if big else "compact", "large_print": bool(body.get("large_print")),
            "out_dir": out_dir, "missing": missing, "blank": blank}


def build_handout(body):
    """Collect the lesson and write the handout PDF. Returns what the page shows when it is done."""
    data = collect_lesson(body)
    out_dir, missing, blank = data["out_dir"], data["missing"], data["blank"]
    _set(step="Writing the handout…", percent=88)
    page = lesson_html(data)
    stem = f"{_safe(data['title'])}_handout_{time.strftime('%Y%m%d-%H%M')}"
    html_path = out_dir / f"{stem}.html"
    html_path.write_text(page, encoding="utf-8")
    pdf = out_dir / f"{stem}.pdf"
    _set(step="Making the PDF…", percent=94)
    if html_to_pdf(html_path, pdf):
        html_path.unlink(missing_ok=True)
        return {"file": str(pdf), "name": pdf.name, "kind": "pdf", "missing": missing, "blank": blank, "pages": _pdf_pages(pdf)}
    return {"file": str(html_path), "name": html_path.name, "kind": "html", "missing": missing, "blank": blank,
            "note": "Microsoft Edge was not found, so the handout was saved as a web page. Open it and choose Print, then Save as PDF."}


def deck_slides(data, per_scene=False):
    """The lesson as slides: title, problem (with its figure), the solution, then each scene as picture slides with the narration in the speaker notes.
    Nothing is closed with a brand slide: the footer on every slide says it was made with Manimo."""
    accent = readable_accent(data["brand"].get("accent") or MANIMO_TEAL).lstrip("#").upper()
    sub = " · ".join(x for x in (data.get("audience"), data.get("date"), data["brand"].get("name")) if x)
    slides = [{"layout": "title", "title": data["title"], "caption": sub, "notes": ""}]
    if data.get("problem"):
        one = {"title": "Problem", "paras": [(data["problem"], False, None)], "notes": "Read the problem aloud, then ask what is given and what is asked."}
        if data.get("figure"):
            one.update(layout="textpicture", image=data["figure"], image_alt="The figure for the problem")
        else:
            one["layout"] = "text"
        slides.append(one)
    sol = parse_solution(data.get("solution"))
    if sol:
        groups, cur = [], []
        for label, text in sol:
            cur.append((label, text))
            if label in ("Method", "Check") or (not label and len(cur) > 1):
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        for gi, g in enumerate(groups):
            paras = []
            for label, text in g:
                if label:
                    paras.append((label, True, "#" + accent))
                for ln in [l.strip() for l in text.splitlines() if l.strip()]:
                    paras.append((ln, label == "Answer", None))
            slides.append({"layout": "text", "title": "Solution" + (f" ({gi + 1} of {len(groups)})" if len(groups) > 1 else ""), "paras": paras, "notes": "Work through the solution step by step."})
    for s in data["sections"]:
        if per_scene:
            frame_ = next((st["frame"] for st in reversed(s["steps"]) if st.get("frame")), None)
            slides.append({"layout": "picture" if frame_ else "text", "title": s["name"], "image": frame_, "image_alt": f"The finished picture of the scene {s['name']}",
                           "caption": "", "paras": [] if frame_ else [(s["narration"] or "This scene has no narration.", False, None)], "notes": s["narration"]})
            continue
        if not s["steps"]:
            slides.append({"layout": "text", "title": s["name"], "paras": [("This scene has no narration.", False, None)], "notes": ""})
        for i, st in enumerate(s["steps"], 1):
            notes = (f"Step {i}: " + st["text"] + "\n\nThe whole scene, as it is spoken:\n" + s["narration"]) if st.get("text") else s["narration"]
            base = {"title": f"{s['name']}: step {i}" if len(s["steps"]) > 1 else s["name"], "notes": notes}
            if st.get("frame"):
                slides.append(dict(base, layout="picture", image=st["frame"], image_alt=f"Step {i} of {s['name']}: " + st.get("text", ""), caption=st.get("text", "")))
            else:
                slides.append(dict(base, layout="text", paras=[(st.get("text") or "", False, None)]))
    for s in slides:                                           # text colours given as "#rrggbb" are passed on without the #
        s["paras"] = [(t, b, c.lstrip("#") if c else None) for t, b, c in s.get("paras", [])]
    return slides, accent


def build_pptx(body):
    """The lesson as a PowerPoint file. One slide for each spoken line (so a diagram builds up as it is explained), or one for each scene."""
    data = collect_lesson(body)
    _set(step="Writing the slides…", percent=90)
    slides, accent = deck_slides(data, per_scene=body.get("slides") == "scene")
    b = data["brand"]
    footer = ("Prepared by " + b["name"] + " · " if b.get("name") else "") + "Made with Manimo · " + SITE.replace("https://", "").rstrip("/")
    path = data["out_dir"] / f"{_safe(data['title'])}_slides_{time.strftime('%Y%m%d-%H%M')}.pptx"
    n = pptx_writer.build(path, {"title": data["title"], "footer": footer, "accent": accent, "slides": slides})
    return {"file": str(path), "name": path.name, "kind": "pptx", "slides": n, "missing": data["missing"], "blank": data["blank"]}


def _pdf_pages(path):
    try:
        return len(re.findall(rb"/Type\s*/Page[^s]", Path(path).read_bytes()))
    except OSError:
        return None


# ---------------------------------------------------------------- GIF and the share folder
def build_gif(body):
    out_dir, ff = _out_dir(body), _ffmpeg()
    video = _scene_video(out_dir, str(body.get("scene") or ""), body.get("video"))
    if not video:
        raise KitError("That video could not be found. Render the scene first.")
    start = max(0.0, float(body.get("start") or 0))
    length = min(30.0, max(1.0, float(body.get("seconds") or 8)))
    width = min(720, max(240, int(body.get("width") or 480)))
    fps = min(20, max(5, int(body.get("fps") or 12)))
    out = out_dir / f"{video.stem}.gif"
    n = 2
    while out.exists():
        out = out_dir / f"{video.stem}_{n}.gif"
        n += 1
    _set(step="Making the GIF…", percent=30)
    vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4"
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(video), "-vf", vf, "-loop", "0", str(out)],
                       capture_output=True, text=True, creationflags=NO_WINDOW, timeout=300)
    if not out.is_file():
        raise KitError("Could not make the GIF: " + (r.stderr or "")[-200:])
    return {"file": str(out), "name": out.name, "kind": "gif", "size": out.stat().st_size}


def _stamp(t):
    t = int(t)
    return f"{t // 60}:{t % 60:02d}" if t < 3600 else f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def build_share(body):
    """One folder to post from: the scenes joined into one video, a cover picture, the title, a description and chapter times."""
    out_dir, ff = _out_dir(body), _ffmpeg()
    vids = [(str(s.get("name")), _scene_video(out_dir, str(s.get("name")), s.get("video"))) for s in (body.get("scenes") or []) if isinstance(s, dict)]
    vids = [(n, v) for n, v in vids if v]
    if not vids:
        raise KitError("Render at least one scene first, then share it.")
    title = " ".join(str(body.get("title") or "Lesson").split())[:100]
    folder = out_dir / f"Share - {_safe(title).replace('_', ' ')}"
    n = 2
    while folder.exists():
        folder = out_dir / f"Share - {_safe(title).replace('_', ' ')} ({n})"
        n += 1
    folder.mkdir()
    _set(step="Joining the scenes…", percent=15)
    lens = [duration(ff, v) for _, v in vids]
    video = folder / f"{_safe(title)}.mp4"
    if len(vids) == 1:
        shutil.copy2(vids[0][1], video)
    else:
        lst = folder / ".list.txt"
        lst.write_text("".join("file '" + str(v).replace("\\", "/").replace("'", "'\\''") + "'\n" for _, v in vids), encoding="utf-8")   # forward slashes first, then quote any '
        r = subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video)], capture_output=True, text=True, creationflags=NO_WINDOW, timeout=600)
        lst.unlink(missing_ok=True)
        if not video.is_file() or video.stat().st_size < 1000:
            r = subprocess.run([ff, "-y", "-loglevel", "error"] + sum((["-i", str(v)] for _, v in vids), []) +
                               ["-filter_complex", "".join(f"[{i}:v][{i}:a]" for i in range(len(vids))) + f"concat=n={len(vids)}:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", str(video)],
                               capture_output=True, text=True, creationflags=NO_WINDOW, timeout=1200)
            if not video.is_file():
                raise KitError("Could not join the scenes: " + (r.stderr or "")[-200:])
    _set(step="Making the cover…", percent=70)
    cover = frame(ff, video, min(max(0.5, sum(lens) * 0.4), max(0.5, sum(lens) - 0.2)), 1280)
    if cover:
        (folder / "cover.jpg").write_bytes(cover)
    t, chapters = 0.0, []
    for (name, _), ln in zip(vids, lens):
        chapters.append(f"{_stamp(t)} {re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name).replace('_', ' ')}")
        t += ln
    (folder / "title.txt").write_text(title + "\n", encoding="utf-8")
    (folder / "chapters.txt").write_text("\n".join(chapters) + "\n", encoding="utf-8")
    desc = [title, ""] + ([str(body["description"]).strip(), ""] if str(body.get("description") or "").strip() else []) + ["Chapters", *chapters, "", "Made with Manimo: " + SITE]
    (folder / "description.txt").write_text("\n".join(desc) + "\n", encoding="utf-8")
    return {"file": str(folder), "name": folder.name, "kind": "folder", "files": sorted(p.name for p in folder.iterdir()), "seconds": round(t, 1)}


# ---------------------------------------------------------------- the routes
def handle(method, path, body):
    if method == "GET" and path == "/api/kit/job":
        return job(), 200
    if method == "GET" and path == "/api/brand":
        return brand_get(), 200
    if method == "POST" and path == "/api/brand":
        return brand_set(body)
    if method == "POST" and path == "/api/kit/pdf":
        return _start("pdf", build_handout, body)
    if method == "POST" and path == "/api/kit/pptx":
        return _start("pptx", build_pptx, body)
    if method == "POST" and path == "/api/kit/gif":
        return _start("gif", build_gif, body)
    if method == "POST" and path == "/api/kit/share":
        return _start("share", build_share, body)
    return {"error": "not found"}, 404
