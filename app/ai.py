"""Manimo AI assistant.

Talks to a language model (Anthropic Claude, or any OpenAI-compatible service), gives it the Manimo "skill" (how to write
explainer-quality Manim/ManimGX code), then checks what it wrote and asks it to fix problems:

    write  ->  check names  ->  check the scene (ManimGX: `manimgx inspect`; Manim CE: a quick render)  ->  fix  ->  ...

Standard library only. The API key is encrypted with Windows DPAPI (tied to the signed-in Windows user) and never sent
to the page.
"""
import base64
import codecs
import ctypes
import difflib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
SKILL_DIR = APP_DIR / "ai" / "skill"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Manimo" / "data"
SETTINGS_FILE = DATA_DIR / "ai.json"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

ANTHROPIC_URL = os.environ.get("MANIMO_ANTHROPIC_URL", "https://api.anthropic.com/v1/messages")
MODELS = [
    ("claude-sonnet-5-5", "Sonnet 5.5 - balanced (recommended)"),
    ("claude-opus-5-5", "Opus 5.5 - highest quality"),
    ("claude-haiku-5-5", "Haiku 5.5 - fastest and cheapest"),
    ("claude-fable-5-1", "Fable 5.1"),
]
DEFAULTS = {"provider": "anthropic", "model": "claude-sonnet-5-5", "base_url": "https://api.openai.com/v1", "visual": False}
MAX_ROUNDS = 3          # write + up to two fix rounds
MAX_SCENES_CHECKED = 4
MAX_TOKENS = 8192
SCENE_CLASS = re.compile(r"^class\s+(\w+)\s*\(([^)]*)\)\s*:", re.M)
SCENE_BASE = re.compile(r"(^|\.)\w*Scene\w*$")
LAYOUT = re.compile(r"^\s*\[(\d+)\]\s+t=(\S+)\s+\((?:[^()]*[\\/])?scene\.py:(\d+)\)\s+(.*)$")
HEADER = re.compile(r"^(?:.*[\\/])?scene\.py:\s*(\w+),\s*([\d.]+)\s*s,\s*(\d+)\s*plays")

_lock = threading.Lock()
_job = {"state": "idle"}
_cancel = threading.Event()
_prompt_cache = {}


class AIError(Exception):
    pass


class Cancelled(Exception):
    pass


# ---------------------------------------------------------------- settings and the encrypted key
def _blob(data):
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    return Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf, Blob


def protect(data):
    if os.name != "nt":
        return base64.b64encode(data)
    blob_in, keep, Blob = _blob(data)
    blob_out = Blob()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(blob_in), "Manimo AI key", None, None, None, 0, ctypes.byref(blob_out)):
        raise AIError("Could not protect the key on this PC.")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def unprotect(data):
    if os.name != "nt":
        return base64.b64decode(data)
    blob_in, keep, Blob = _blob(data)
    blob_out = Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise AIError("The saved key could not be read. Enter it again.")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def load_settings():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def api_key(cfg=None):
    cfg = cfg or load_settings()
    blob = cfg.get("key_enc")
    if not blob:
        return ""
    try:
        return unprotect(base64.b64decode(blob)).decode("utf-8")
    except Exception:
        return ""


def public_settings():
    cfg = load_settings()
    agents = detect_agents()
    if not cfg.get("agent") and agents:
        cfg["agent"] = agents[0]["id"]
    return {
        "provider": cfg["provider"], "model": cfg["model"], "base_url": cfg["base_url"], "visual": bool(cfg.get("visual")),
        "has_key": bool(cfg.get("key_enc")) , "models": [{"id": i, "label": l} for i, l in MODELS],
        "agents": agents, "agent": cfg.get("agent", ""), "agent_model": cfg.get("agent_model", ""),
        "configured": bool(cfg.get("key_enc")) or (cfg["provider"] == "openai" and "localhost" in cfg["base_url"])
                      or (cfg["provider"] == "agent" and any(a["id"] == cfg.get("agent") for a in agents)),
    }


def save_settings(body):
    cfg = load_settings()
    if body.get("provider") in ("anthropic", "openai", "agent"):
        cfg["provider"] = body["provider"]
    if body.get("agent") in AGENTS:
        cfg["agent"] = body["agent"]
    if isinstance(body.get("agent_model"), str):
        cfg["agent_model"] = re.sub(r"[^\w.\-:/]", "", body["agent_model"])[:80]
    if isinstance(body.get("model"), str) and body["model"].strip():
        cfg["model"] = body["model"].strip()[:120]
    if isinstance(body.get("base_url"), str) and body["base_url"].strip():
        cfg["base_url"] = body["base_url"].strip().rstrip("/")[:300]
    if "visual" in body:
        cfg["visual"] = bool(body["visual"])
    key = body.get("api_key")
    if isinstance(key, str):
        key = key.strip()
        if key:
            cfg["key_enc"] = base64.b64encode(protect(key.encode("utf-8"))).decode("ascii")
        elif body.get("clear_key"):
            cfg.pop("key_enc", None)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(cfg), encoding="utf-8")
    return public_settings()


# ---------------------------------------------------------------- the skill prompt
def _read(name):
    return (SKILL_DIR / name).read_text(encoding="utf-8")


def valid_names():
    try:
        return json.loads((APP_DIR / "ai" / "names.json").read_text(encoding="utf-8"))
    except Exception:
        return {"top": [], "modules": [], "scene": [], "mobject": []}


def skill_prompt(engine):
    """The system prompt: role, style guide, engine rules, valid names, and worked examples."""
    if engine in _prompt_cache:
        return _prompt_cache[engine]
    parts = [
        "You are Manimo's animation director. You write complete, runnable Python files that explain ideas visually, "
        "the way the best maths-explainer channels do. Follow the guide below exactly.",
        _read("style_guide.md"),
        _read("manimgx.md" if engine == "manimgx" else "manim_ce.md"),
    ]
    if engine == "manimgx":
        names = valid_names()
        groups = {"class": [], "function": [], "constant": [], "variable": []}
        for item in names.get("top", []):
            n, _, k = item.partition(":")
            groups.setdefault(k, []).append(n)
        parts.append(
            "## Valid names (use only these after `m.`)\n"
            f"Classes: {', '.join(groups['class'])}\n\nFunctions: {', '.join(groups['function'])}\n\n"
            f"Constants: {', '.join(groups['constant'])}\n\nOther: {', '.join(groups['variable'])}\n\n"
            f"Scene methods: {', '.join(names.get('scene', []))}")
        examples = ["unit_circle_sine.py", "pythagoras_squares.py", "derivative_tangent.py", "binary_search.py"]
    else:
        examples = ["ce_example.py"]
    shown = []
    for ex in examples:
        shown.append(f"### Example: {ex}\n```python\n{_read('examples/' + ex).rstrip()}\n```")
    parts.append("## Worked examples (study their structure, pacing and layout)\n\n" + "\n\n".join(shown))
    _prompt_cache[engine] = "\n\n".join(parts)
    return _prompt_cache[engine]


def build_user_message(req):
    """The latest user turn, with the editor's context attached."""
    mode, text = req.get("mode", "write"), (req.get("prompt") or "").strip()
    code, selection, error = req.get("code") or "", req.get("selection") or "", req.get("error") or ""
    blocks = []
    if code.strip() and req.get("use_code", True):
        blocks.append(f"<current_code>\n{code}\n</current_code>")
    if selection.strip():
        blocks.append(f"<selected_code>\n{selection}\n</selected_code>")
    if error.strip():
        blocks.append(f"<last_error>\n{error[-3000:]}\n</last_error>")
    guide = {
        "write": "Write a new complete scene file for this request. If <current_code> is given it is only context.",
        "edit": "Change <current_code> as asked. Keep the user's names and structure; return the complete updated file.",
        "fix": "Fix the problem in <current_code> using <last_error>. Change only what is needed; return the complete file.",
        "improve": "Improve the visual quality of <current_code> (layout, pacing, colour, clarity) without changing what it teaches. Return the complete file.",
        "explain": "Explain <current_code> in plain language for someone who does not know Python. Do not return code.",
        "chat": "Answer the question. Only return code if it is asked for.",
    }.get(mode, "")
    blocks.append(f"<request>\n{text or guide}\n</request>")
    if text and guide:
        blocks.append(f"<how_to_respond>\n{guide}\n</how_to_respond>")
    return "\n\n".join(blocks)


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    blocks = [b for b in blocks if "import" in b or "class " in b]
    return blocks[-1].strip("\n") + "\n" if blocks else ""


# ---------------------------------------------------------------- talking to the model
def _friendly_http(status, body):
    detail = ""
    try:
        j = json.loads(body.decode("utf-8", "replace"))
        detail = (j.get("error") or {}).get("message") or j.get("message") or ""
    except Exception:
        pass
    table = {
        401: "The API key was rejected. Check it in AI settings.",
        403: "The provider refused this request (permission or region).",
        404: "That model was not found. Pick another model in AI settings.",
        413: "The request was too large.",
        429: "The provider says you are out of quota or sending too fast. Wait a moment or check your plan.",
        529: "The provider is overloaded right now. Try again in a minute.",
    }
    msg = table.get(status) or (f"The provider returned an error ({status})." if status < 500 else "The provider had a problem. Try again shortly.")
    return msg + (f" ({detail[:200]})" if detail and status not in (401,) else "")


def _open(req, timeout=90):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise AIError(_friendly_http(e.code, e.read()))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise AIError("Could not reach the AI provider. Check your internet connection. (%s)" % getattr(e, "reason", e))


def stream_anthropic(cfg, system, messages, on_delta, max_tokens=MAX_TOKENS):
    body = {"model": cfg["model"], "max_tokens": max_tokens, "stream": True, "messages": messages,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]}
    req = urllib.request.Request(ANTHROPIC_URL, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "content-type": "application/json", "x-api-key": api_key(cfg), "anthropic-version": "2023-06-01"})
    resp = _open(req)
    try:
        for raw in resp:
            if _cancel.is_set():
                raise Cancelled()
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                data = json.loads(line[5:].strip())
            except ValueError:
                continue
            kind = data.get("type")
            if kind == "content_block_delta" and (data.get("delta") or {}).get("type") == "text_delta":
                on_delta(data["delta"]["text"])
            elif kind == "error":
                raise AIError((data.get("error") or {}).get("message", "The provider reported an error."))
    finally:
        resp.close()


def stream_openai(cfg, system, messages, on_delta, max_tokens=MAX_TOKENS):
    flat = []
    for m in messages:
        content = m["content"]
        if isinstance(content, list):
            content = "\n".join(p.get("text", "") for p in content if p.get("type") == "text")
        flat.append({"role": m["role"], "content": content})
    body = {"model": cfg["model"], "stream": True, "max_tokens": max_tokens, "messages": [{"role": "system", "content": system}] + flat}
    headers = {"content-type": "application/json"}
    key = api_key(cfg)
    if key:
        headers["authorization"] = "Bearer " + key
    req = urllib.request.Request(cfg["base_url"].rstrip("/") + "/chat/completions", data=json.dumps(body).encode("utf-8"), method="POST", headers=headers)
    resp = _open(req, timeout=180)
    try:
        for raw in resp:
            if _cancel.is_set():
                raise Cancelled()
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                delta = json.loads(payload)["choices"][0].get("delta", {}).get("content")
            except (ValueError, KeyError, IndexError):
                continue
            if delta:
                on_delta(delta)
    finally:
        resp.close()


# Coding agents already installed on this PC. They are used as plain text writers (tools switched off), with the
# user's own sign-in, so no API key is needed. Only Claude Code has been tried end to end; the others follow their documented headless modes.
AGENTS = {
    "claude": {"label": "Claude Code", "exe": "claude",
               "args": ["-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages", "--tools", "", "--no-session-persistence",
                        "--disable-slash-commands", "--strict-mcp-config"],
               "model_flag": "--model", "stream_json": True},
    "codex": {"label": "Codex CLI", "exe": "codex", "args": ["exec", "--skip-git-repo-check", "-s", "read-only", "-"], "model_flag": "-m"},
    "gemini": {"label": "Gemini CLI", "exe": "gemini", "args": ["-p", " "], "model_flag": "-m"},
}


def detect_agents():
    out = []
    for key, a in AGENTS.items():
        path = shutil.which(a["exe"])
        if path:
            out.append({"id": key, "label": a["label"], "path": path})
    return out


def _agent_prompt(system, messages):
    parts = ["INSTRUCTIONS (follow them exactly):\n" + system, "\nCONVERSATION SO FAR:"]
    for m in messages:
        who = "User" if m["role"] == "user" else "Assistant (you)"
        parts.append("\n[%s]\n%s" % (who, m["content"] if isinstance(m["content"], str) else ""))
    parts.append("\nWrite only your next reply as the assistant. Do not use any tools; answer in text.")
    return "\n".join(parts)


def stream_agent(cfg, system, messages, on_delta, max_tokens=MAX_TOKENS):
    a = AGENTS.get(cfg.get("agent") or "")
    path = shutil.which(a["exe"]) if a else None
    if not a or not path:
        raise AIError("Manimo could not find a coding agent on this PC. Install one and sign in, or use an API key instead.")
    cmd = [path] + a["args"]
    if cfg.get("agent_model"):
        cmd += [a["model_flag"], cfg["agent_model"]]
    cwd = DATA_DIR / "agent-cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd), creationflags=NO_WINDOW)
    except OSError as e:
        raise AIError("Could not start %s: %s" % (a["label"], e))
    err = []
    threading.Thread(target=lambda: err.append(proc.stderr.read()), daemon=True).start()

    def feed():
        try:
            proc.stdin.write(_agent_prompt(system, messages).encode("utf-8"))
            proc.stdin.close()
        except OSError:
            pass
    threading.Thread(target=feed, daemon=True).start()
    dec = codecs.getincrementaldecoder("utf-8")("replace")
    got = False
    failure = ""
    try:
        if a.get("stream_json"):
            for raw in iter(proc.stdout.readline, b""):
                if _cancel.is_set():
                    raise Cancelled()
                try:
                    ev = json.loads(raw.decode("utf-8", "replace"))
                except ValueError:
                    continue
                if ev.get("type") == "stream_event":
                    d = (ev.get("event") or {}).get("delta") or {}
                    if d.get("type") == "text_delta" and d.get("text"):
                        got = True
                        on_delta(d["text"])
                elif ev.get("type") == "result":
                    if ev.get("is_error"):
                        failure = str(ev.get("result") or "")
                    elif not got and ev.get("result"):      # nothing streamed: use the final text
                        got = True
                        on_delta(str(ev["result"]))
        else:
            while True:
                if _cancel.is_set():
                    raise Cancelled()
                chunk = proc.stdout.read1(4096) if hasattr(proc.stdout, "read1") else proc.stdout.read(4096)
                if not chunk:
                    break
                piece = dec.decode(chunk)
                if piece:
                    got = True
                    on_delta(piece)
    finally:
        if proc.poll() is None:
            proc.kill()
    proc.wait()
    if (proc.returncode not in (0, None) or failure) and not got:
        msg = failure or (b"".join(err).decode("utf-8", "replace") if err else "").strip()
        low = msg.lower()
        if any(w in low for w in ("login", "sign in", "authenticate", "api key", "unauthorized", "401")):
            raise AIError("%s is not signed in. Open it once in a terminal and sign in, then try again." % a["label"])
        raise AIError("%s stopped with an error. %s" % (a["label"], msg[-300:]))
    if not got:
        raise AIError("%s returned nothing. Try again." % a["label"])


def stream(cfg, system, messages, on_delta, max_tokens=MAX_TOKENS):
    fn = {"anthropic": stream_anthropic, "agent": stream_agent}.get(cfg["provider"], stream_openai)
    fn(cfg, system, messages, on_delta, max_tokens)


def test_connection():
    cfg = load_settings()
    if cfg["provider"] == "agent" and not cfg.get("agent"):
        return {"ok": False, "error": "Pick an installed agent first."}
    if not api_key(cfg) and cfg["provider"] == "anthropic":
        return {"ok": False, "error": "Enter an API key first."}
    got = []
    _cancel.clear()
    try:
        stream(cfg, "Reply with the single word OK.", [{"role": "user", "content": "ping"}], got.append, max_tokens=16)
    except AIError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "reply": "".join(got).strip()[:40]}


# ---------------------------------------------------------------- checking what the model wrote
def find_scenes(code):
    names = []
    for m in SCENE_CLASS.finditer(code):
        if any(SCENE_BASE.search(b.strip()) for b in m.group(2).split(",")):
            names.append(m.group(1))
    return names


def check_names(code):
    """Every m.Something must exist in ManimGX. Returns issues with the line and a likely fix."""
    names = valid_names()
    if not names.get("top"):
        return []
    known = {n.partition(":")[0] for n in names["top"]} | set(names.get("modules", [])) | {"config"}
    alias = {"m"}
    for mt in re.finditer(r"^\s*import\s+manimgx\s+as\s+(\w+)", code, re.M):
        alias.add(mt.group(1))
    issues, seen = [], set()
    for i, line in enumerate(code.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for a in alias:
            for mt in re.finditer(r"\b%s\.([A-Za-z_]\w*)" % re.escape(a), line):
                n = mt.group(1)
                if n not in known and (i, n) not in seen:
                    seen.add((i, n))
                    guess = difflib.get_close_matches(n, known, n=3, cutoff=0.6)
                    issues.append({"kind": "name", "line": i, "text": f"`{a}.{n}` does not exist in ManimGX" +
                                   (f". Did you mean {', '.join(a + '.' + g for g in guess)}?" if guess else ".")})
    return issues


SAFE_IMPORTS = {"manimgx", "manim", "numpy", "math", "random", "itertools", "functools", "typing", "dataclasses", "colorsys", "collections",
                "fractions", "decimal", "enum", "abc", "copy", "operator", "__future__", "statistics", "cmath", "string", "textwrap"}
FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "exit", "quit"}
FORBIDDEN_ATTRS = {"__subclasses__", "__globals__", "__builtins__", "__import__", "__code__", "__bases__", "__mro__", "__loader__"}


def scan_code(code):
    """A best-effort guard (not a sandbox): generated code is run to be checked before the user has read it, so refuse
    anything that touches files, the network or the system. Returns issues in the same shape as check_names."""
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []          # the real check reports syntax errors with their line
    issues = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in SAFE_IMPORTS:
                    issues.append({"kind": "safety", "line": line, "text": f"`import {a.name}` is not allowed: animations must not use files, the network or the system"})
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in SAFE_IMPORTS:
                issues.append({"kind": "safety", "line": line, "text": f"`from {node.module or '.'} import ...` is not allowed: animations must not use files, the network or the system"})
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            issues.append({"kind": "safety", "line": line, "text": f"`{node.func.id}(...)` is not allowed in an animation"})
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            issues.append({"kind": "safety", "line": line, "text": f"`.{node.attr}` is not allowed in an animation"})
    return issues


def _clean(text):
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text or "")


def parse_inspect(stdout, stderr, returncode):
    out, err = _clean(stdout), _clean(stderr)
    res = {"error": None, "problems": [], "header": None, "ok": False}
    for line in out.splitlines():
        h = HEADER.match(line.strip())
        if h:
            res["header"] = {"scene": h.group(1), "seconds": float(h.group(2)), "plays": int(h.group(3))}
        m = LAYOUT.match(line)
        if m:
            res["problems"].append({"kind": "layout", "n": int(m.group(1)), "t": m.group(2), "line": int(m.group(3)), "text": m.group(4).strip()})
    if "layout:" not in out:
        text = (err.strip() or out.strip())[-1400:]
        ln = None
        m = re.findall(r"scene\.py:(\d+): in", text) or re.findall(r"scene\.py, line (\d+)\)", text) or re.findall(r'line (\d+)', text)
        if m:
            ln = int(m[-1])
        res["error"] = {"kind": "error", "line": ln, "text": text or "The scene could not be checked."}
    res["ok"] = res["error"] is None and not res["problems"]
    return res


def verify_manimgx(code, workdir, scenes, step_cb=None):
    src = workdir / "scene.py"
    src.write_text(code, encoding="utf-8")
    report = {"engine": "manimgx", "scenes": [], "problems": [], "error": None, "images": [], "skipped": 0}
    targets = scenes[:MAX_SCENES_CHECKED]
    report["skipped"] = max(0, len(scenes) - len(targets))
    for sc in targets:
        if _cancel.is_set():
            raise Cancelled()
        png = workdir / f"{sc}.storyboard.png"
        try:
            p = subprocess.run([sys.executable, "-m", "manimgx", "inspect", str(src), sc, "-o", str(png)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=180, cwd=workdir, creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired:
            report["error"] = {"kind": "error", "line": None, "text": f"Checking {sc} took longer than 3 minutes. The scene may loop forever or be extremely heavy."}
            return report
        r = parse_inspect(p.stdout, p.stderr, p.returncode)
        if r["error"]:
            report["error"] = r["error"]
            return report
        report["scenes"].append(r["header"] or {"scene": sc})
        for pr in r["problems"]:
            pr["scene"] = sc
            report["problems"].append(pr)
        if png.exists():
            report["images"].append(str(png))
    return report


def verify_manim(code, workdir, scenes):
    report = {"engine": "manim", "scenes": [], "problems": [], "error": None, "images": [], "skipped": 0, "note": ""}
    try:
        compile(code, "scene.py", "exec")
    except SyntaxError as e:
        report["error"] = {"kind": "error", "line": e.lineno, "text": f"SyntaxError: {e.msg} (line {e.lineno})"}
        return report
    if not scenes:
        report["error"] = {"kind": "error", "line": None, "text": "No Scene class found. The file needs a class that extends Scene."}
        return report
    import importlib.util
    if importlib.util.find_spec("manim") is None:
        report["note"] = "Manim is not added yet, so only the syntax was checked."
        return report
    src = workdir / "scene.py"
    src.write_text(code, encoding="utf-8")
    try:
        p = subprocess.run([sys.executable, "-m", "manim", "render", str(src), scenes[0], "-ql", "--media_dir", str(workdir / "media"),
                            "--disable_caching", "--progress_bar", "none"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=240, cwd=workdir, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        report["error"] = {"kind": "error", "line": None, "text": "The test render took longer than 4 minutes."}
        return report
    if p.returncode != 0:
        text = _clean((p.stderr or "") + "\n" + (p.stdout or "")).strip()
        lines = re.findall(r'scene\.py", line (\d+)', text)
        tail = [l for l in text.splitlines() if l.strip()][-6:]
        report["error"] = {"kind": "error", "line": int(lines[-1]) if lines else None, "text": "\n".join(tail)}
    else:
        report["scenes"].append({"scene": scenes[0]})
    return report


def feedback_for(report, name_issues, code):
    lines_of = code.splitlines()
    items = []

    def line_text(n):
        return lines_of[n - 1].strip() if isinstance(n, int) and 1 <= n <= len(lines_of) else ""
    for it in name_issues:
        items.append(f"- line {it['line']}: {it['text']}   (`{line_text(it['line'])}`)")
    if report.get("error"):
        e = report["error"]
        where = f" at line {e['line']}" if e.get("line") else ""
        items.append(f"- the scene stopped with an error{where}:\n```\n{e['text']}\n```")
    for pr in report.get("problems", [])[:12]:
        items.append(f"- layout, scene {pr.get('scene', '')}, line {pr['line']}, at {pr['t']}: {pr['text']}   (`{line_text(pr['line'])}`)")
    return ("The automatic check found problems in your code:\n" + "\n".join(items) +
            "\n\nFix every one of them. Keep everything else as it is. Return the complete file in one ```python block, "
            "then one line saying what you changed.")


# ---------------------------------------------------------------- the job
def _update(**kw):
    with _lock:
        _job.update(kw)


def _step(label, detail=""):
    with _lock:
        _job["steps"].append({"label": label, "state": "running", "detail": detail})
        return len(_job["steps"]) - 1


def _finish(i, state="done", detail=None):
    with _lock:
        if i < len(_job["steps"]):
            _job["steps"][i]["state"] = state
            if detail is not None:
                _job["steps"][i]["detail"] = detail


def _image_block(path):
    try:
        data = Path(path).read_bytes()
        if len(data) > 3_500_000:
            return None
        return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(data).decode("ascii")}}
    except OSError:
        return None


def run(req):
    cfg = load_settings()
    engine = "manim" if req.get("engine") == "manim" else "manimgx"
    mode = req.get("mode") or "write"
    workdir = Path(tempfile.mkdtemp(prefix="manimo-ai-"))
    try:
        system = skill_prompt(engine)
        history = [m for m in (req.get("history") or []) if m.get("role") in ("user", "assistant") and str(m.get("text", "")).strip()][-12:]
        messages = [{"role": m["role"], "content": str(m["text"])[:20000]} for m in history]
        while messages and messages[0]["role"] != "user":
            messages.pop(0)
        if messages and messages[-1]["role"] == "user":
            messages.pop()
        messages.append({"role": "user", "content": build_user_message(req)})
        wants_code = mode not in ("explain", "chat")
        rounds_allowed = MAX_ROUNDS if wants_code else 1
        final_text, final_code, report, name_issues = "", "", None, []
        t0 = time.time()
        for rnd in range(1, rounds_allowed + 1):
            if not wants_code:
                label = "Thinking"
            elif rnd == 1:
                label = "Writing the scene"
            else:
                label = "Fixing the problems (round %d)" % rnd
            idx = _step(label, "starting %s, the first words can take 20 seconds" % AGENTS.get(cfg.get("agent"), {}).get("label", "the assistant") if cfg["provider"] == "agent" else "")
            buf = []

            def on_delta(piece, buf=buf):
                buf.append(piece)
                _update(text="".join(buf))
            stream(cfg, system, messages, on_delta)
            text = "".join(buf)
            code = extract_code(text)
            _finish(idx, "done", f"{len(code.splitlines())} lines" if code else "")
            final_text = text
            if not wants_code or not code:
                final_code = code
                break
            final_code = code
            scenes = find_scenes(code)
            if engine == "manimgx":
                i1 = _step("Checking that every name exists")
                name_issues = check_names(code)
                _finish(i1, "warn" if name_issues else "done", f"{len(name_issues)} unknown" if name_issues else "all names are real")
            else:
                name_issues = []
            i0 = _step("Checking the code is safe to run")
            unsafe = scan_code(code)
            _finish(i0, "warn" if unsafe else "done", f"{len(unsafe)} not allowed" if unsafe else "no file, network or system access")
            name_issues = name_issues + unsafe
            i2 = _step("Checking for errors and layout problems" if engine == "manimgx" else "Test-rendering the scene")
            if unsafe:     # never run code that asks for system access
                report = {"engine": engine, "scenes": [], "problems": [], "error": None, "images": [], "skipped": 0, "note": "Not run: it asks for file, network or system access."}
            elif engine == "manimgx":
                report = verify_manimgx(code, workdir, scenes)
            else:
                report = verify_manim(code, workdir, scenes)
            n_issue = len(name_issues) + len(report["problems"]) + (1 if report["error"] else 0)
            if n_issue:
                _finish(i2, "warn", f"{n_issue} problem{'s' if n_issue != 1 else ''} found")
            else:
                s = report["scenes"][0] if report["scenes"] else {}
                _finish(i2, "done", (f"{s.get('plays', '?')} animations, {s.get('seconds', 0):.0f} s, clean" if s.get("plays") else "clean") + (" " + report.get("note", "") if report.get("note") else ""))
            if not n_issue:
                break
            if rnd == rounds_allowed:
                break
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": feedback_for(report, name_issues, code)})
        # optional: let the model look at the storyboard once
        remaining = (len(name_issues) + len(report["problems"]) + (1 if report["error"] else 0)) if report else 0
        if wants_code and final_code and report and not remaining and cfg.get("visual") and cfg["provider"] == "anthropic" and report.get("images"):
            img = _image_block(report["images"][0])
            if img:
                i3 = _step("Looking at the storyboard")
                messages.append({"role": "assistant", "content": final_text})
                messages.append({"role": "user", "content": [img, {"type": "text", "text":
                    "This is the storyboard (frames at the end of each animation) of your scene. Look for text overlapping shapes, things outside "
                    "the frame, cramped or tiny labels, and anything unclear. If everything looks good reply with exactly: LOOKS GOOD. "
                    "Otherwise return the complete corrected file in one ```python block and one line saying what you changed."}]})
                buf = []
                stream(cfg, system, messages, lambda p: buf.append(p))
                review = "".join(buf)
                fixed = extract_code(review) if "LOOKS GOOD" not in review else ""
                if fixed:
                    _finish(i3, "warn", "adjusted after looking")
                    re_report = verify_manimgx(fixed, workdir, find_scenes(fixed))
                    if not (re_report["error"] or re_report["problems"] or check_names(fixed)):
                        final_code, final_text, report = fixed, review, re_report
                    else:
                        _finish(i3, "warn", "its adjustment introduced problems, so it was not used")
                else:
                    _finish(i3, "done", "looks good")
        remaining = (len(name_issues) + len(report["problems"]) + (1 if report["error"] else 0)) if report else 0
        summary = None
        if report:
            s = report["scenes"][0] if report["scenes"] else {}
            summary = {"clean": remaining == 0, "problems": [{"line": p["line"], "text": p["text"], "t": p.get("t", ""), "scene": p.get("scene", "")} for p in report["problems"]] +
                       [{"line": i["line"], "text": i["text"], "t": "", "scene": ""} for i in name_issues],
                       "error": report["error"], "seconds": s.get("seconds"), "plays": s.get("plays"), "note": report.get("note", ""),
                       "skipped": report.get("skipped", 0), "rounds": len([x for x in _job["steps"] if x["label"].startswith(("Writing", "Fixing"))]),
                       "elapsed": round(time.time() - t0, 1)}
        _update(state="done", final={"text": final_text, "code": final_code, "report": summary})
    except Cancelled:
        _update(state="cancelled")
    except AIError as e:
        _update(state="error", error=str(e))
    except Exception as e:  # never leave the page waiting
        _update(state="error", error="The assistant stopped unexpectedly: %r" % (e,))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def start(req):
    cfg = load_settings()
    if cfg["provider"] == "anthropic" and not api_key(cfg):
        return {"error": "Add your API key in AI settings first."}, 400
    if cfg["provider"] == "agent" and not cfg.get("agent"):
        return {"error": "Pick an installed agent in AI settings first."}, 400
    with _lock:
        if _job.get("state") == "running":
            return {"error": "The assistant is already working."}, 409
        _job.clear()
        _job.update({"state": "running", "id": secrets.token_hex(4), "text": "", "steps": [], "final": None, "error": None, "mode": req.get("mode", "write")})
    _cancel.clear()
    threading.Thread(target=run, args=(req,), daemon=True).start()
    return {"ok": True}, 200


def cancel():
    _cancel.set()
    return {"ok": True}, 200


def job():
    with _lock:
        return json.loads(json.dumps(_job))


def handle(method, path, body):
    """Routes used by server.py. Returns (payload, status)."""
    if method == "GET" and path == "/api/ai/status":
        return public_settings(), 200
    if method == "GET" and path == "/api/ai/job":
        return job(), 200
    if method == "POST" and path == "/api/ai/settings":
        try:
            return save_settings(body), 200
        except AIError as e:
            return {"error": str(e)}, 500
    if method == "POST" and path == "/api/ai/test":
        return test_connection(), 200
    if method == "POST" and path == "/api/ai/run":
        return start(body)
    if method == "POST" and path == "/api/ai/cancel":
        return cancel()
    return {"error": "not found"}, 404
