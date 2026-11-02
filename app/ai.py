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


# Extra guides are added only when the request needs them: the full pack is large and most requests need none of it.
# Each rule: (name, words that trigger it, reference files, example files).
_GUIDES = [
    ("narrate", r"narrat|voice|speak|spoken|say\(|explain as it plays|teaching video|lesson video",
     ["reveal-and-sync.md"], []),
    ("problem", r"\bproblems?\b|\bsolve\b|solution to|free.?body|\bfbd\b|statics|truss|\bbeam\b|support reaction|friction|incline|projectile|"
                r"kinematic|equilibrium|resultant|moment about|textbook",
     ["problem-solving-pipeline.md", "mechanics-visuals.md", "geometry-visuals.md", "helpers.md"],
     ["incline_block_friction.py", "beam_reactions.py"]),
    ("theory", r"\btheory\b|derive\b|derivation|quantum|schr.dinger|thermodynamic|entropy|partition function|statistical mechanics|"
               r"maxwell|electromagnet|relativity|lagrangian|hamiltonian|fourier|wave function|eigen|boltzmann|orbital",
     ["theory-explainer-pipeline.md", "theory-visuals.md", "theory-playbooks.md", "theory-exam-and-mistakes.md"], []),
    ("exam", r"first.?year|\bexam\b|\bmarks?\b|beginner|they miss steps|model answer",
     ["first-year-exam-mode.md"], []),
]
_NOT_SHIPPED = re.compile(r"[^.\n]*`[\w\-]*_manimo\.py`[^.\n]*\.|\s*Worked example: `[\w\-]*_manimo\.py`[^\n]*")


def _guide(name):
    """A reference file, without sentences that point at example files this app does not ship."""
    return _NOT_SHIPPED.sub("", _read("references/" + name))


def skill_extras(text):
    """Which guides and examples a request needs, from its words: (reference names, example names), in a stable order."""
    t = (text or "").lower()
    refs, examples = [], []
    for _name, pattern, rs, es in _GUIDES:
        if re.search(pattern, t):
            refs += [r for r in rs if r not in refs]
            examples += [e for e in es if e not in examples]
    return refs, examples


def skill_prompt(engine, request_text=""):
    """The system prompt: role, style guide, engine rules, valid names, worked examples, and the guides this request needs."""
    refs, extra_examples = skill_extras(request_text) if engine == "manimgx" else ([], [])
    key = (engine, tuple(refs))
    if key in _prompt_cache:
        return _prompt_cache[key]
    parts = [
        "You are Manimo's animation director. You write complete, runnable Python files that explain ideas visually, "
        "the way the best maths-explainer channels do. Follow the guide below exactly.",
        _read("style_guide.md"),
        _read("manimgx.md" if engine == "manimgx" else "manim_ce.md"),
        _read("modes.md"),
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
    examples = examples + [e for e in extra_examples if e not in examples][:2]
    shown = []
    for ex in examples:
        shown.append(f"### Example: {ex}\n```python\n{_read('examples/' + ex).rstrip()}\n```")
    parts.append("## Worked examples (study their structure, pacing and layout)\n\n" + "\n\n".join(shown))
    if refs:
        parts.append("## Guides for this request\n\n" + "\n\n".join(_guide(r).rstrip() for r in refs))
    _prompt_cache[key] = "\n\n".join(parts)
    return _prompt_cache[key]


SOLVE_SYSTEM = (
    "You are a careful physics and mathematics teacher. Solve the problem the user gives, then check it. "
    "Reply in plain text only: no code and no animation yet. Use exactly this layout:\n"
    "Given: every value with its unit.\nFind: what is asked.\nMethod: the principle or law you use, by name.\n"
    "Steps: numbered, one equation per step, units on every line.\nAnswer: the final values with units, to 3 significant figures.\n"
    "Check: one independent check (units, a limit, or substituting back).\n"
    "If a value is unreadable or ambiguous say which one and what you assumed. Never state a number you have not worked out. Keep it under 350 words.")
READ_SYSTEM = (
    "You read a photo or screenshot of a physics, engineering, maths or science problem and write it down as plain text. Do NOT solve it. "
    "Reply with exactly these lines and nothing else:\n"
    "Problem: the full statement, word for word.\nGiven: every number with its unit, copied exactly.\nFind: what is asked.\n"
    "Figure: what the diagram shows (bodies, supports, ropes, angles with the line each is measured from, dimensions, loads, which way is up).\n"
    "Unclear: anything blurred or missing, and what you assumed. Write [unreadable] for a value you cannot read. Never guess a number silently.")


def solve_prompt():
    """The system prompt for the 'solve first' step: short, with only the solving stages of the problem guide."""
    guide = _guide("problem-solving-pipeline.md")
    cut = guide.find("## Stage 4")
    return SOLVE_SYSTEM + "\n\n" + (guide[:cut] if cut > 0 else guide)


EDIT_VERBS = re.compile(r"^\s*(fix|change|make|improve|add|remove|slow|speed|rename|move|colou?r|shorten|lengthen)\b", re.I)


def wants_solve_first(req, mode):
    """Solve-first applies to a new problem to solve (not to an edit of existing code) when the user left it switched on."""
    text = str(req.get("prompt") or "")
    return (bool(req.get("solve_first")) and mode in ("write", "edit") and len(text) >= 40 and not EDIT_VERBS.match(text)
            and "problem-solving-pipeline.md" in skill_extras(text)[0])


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
        "solve": "Solve the problem in <request> completely and check it. Reply in plain text only (no code, no animation yet), under 350 words.",
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
            if any(p.get("type") == "image" for p in content):          # a service that can see pictures: send it the OpenAI way
                parts = []
                for p in content:
                    if p.get("type") == "image":
                        s = p["source"]
                        parts.append({"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (s["media_type"], s["data"])}})
                    elif p.get("type") == "text":
                        parts.append({"type": "text", "text": p.get("text", "")})
                content = parts
            else:
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
        c = m["content"]
        parts.append("\n[%s]\n%s" % (who, c if isinstance(c, str) else "\n".join(p.get("text", "") for p in c if p.get("type") == "text")))
    parts.append("\nWrite only your next reply as the assistant. Do not use any tools; answer in text.")
    return "\n".join(parts)


def _agent_images(messages):
    """The picture blocks in the last message, if any (only the picture-reading step sends one)."""
    last = messages[-1]["content"] if messages else ""
    return [p for p in last if p.get("type") == "image"] if isinstance(last, list) else []


def stream_agent(cfg, system, messages, on_delta, max_tokens=MAX_TOKENS):
    a = AGENTS.get(cfg.get("agent") or "")
    path = shutil.which(a["exe"]) if a else None
    if not a or not path:
        raise AIError("Manimo could not find a coding agent on this PC. Install one and sign in, or use an API key instead.")
    images = _agent_images(messages)
    if images and not a.get("stream_json"):
        raise AIError("%s cannot look at pictures from Manimo. Type the problem instead, or use Claude Code or an API key." % a["label"])
    cmd = [path] + a["args"] + (["--input-format", "stream-json"] if images else [])
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
            if images:       # one stream-json user turn holding the picture and the instructions
                line = {"type": "user", "message": {"role": "user", "content": images + [{"type": "text", "text": _agent_prompt(system, messages)}]}}
                proc.stdin.write((json.dumps(line) + "\n").encode("utf-8"))
            else:
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
    try:
        return _stream_once(cfg, system, messages, on_delta, max_tokens)
    except AIError as e:
        if cfg["provider"] == "agent" and cfg.get("agent_model") and "selected model" in str(e):
            # the agent does not know the saved model name: try once with the agent's own default instead of failing
            return _stream_once(dict(cfg, agent_model=""), system, messages, on_delta, max_tokens)
        raise


def _stream_once(cfg, system, messages, on_delta, max_tokens=MAX_TOKENS):
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
            p = subprocess.run([sys.executable, str(APP_DIR / "run_with_voice.py"), "inspect", str(src), sc, "-o", str(png)], capture_output=True, text=True,
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
    if wants_solve_first(req, mode):
        mode = "solve"
        req = dict(req, mode="solve", use_code=False, code="", selection="")
    workdir = Path(tempfile.mkdtemp(prefix="manimo-ai-"))
    try:
        recent = [str(m.get("text", "")) for m in (req.get("history") or [])[-4:] if m.get("role") == "user"]
        system = solve_prompt() if mode == "solve" else skill_prompt(engine, " ".join([str(req.get("prompt") or "")] + recent))
        history = [m for m in (req.get("history") or []) if m.get("role") in ("user", "assistant") and str(m.get("text", "")).strip()][-12:]
        messages = [{"role": m["role"], "content": str(m["text"])[:20000]} for m in history]
        while messages and messages[0]["role"] != "user":
            messages.pop(0)
        if messages and messages[-1]["role"] == "user":
            messages.pop()
        messages.append({"role": "user", "content": build_user_message(req)})
        wants_code = mode not in ("explain", "chat", "solve")
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
            stream(cfg, system, messages, on_delta, 2200 if mode == "solve" else MAX_TOKENS)
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
        _update(state="done", final={"text": final_text, "code": final_code, "report": summary, "kind": "solve" if mode == "solve" else ""})
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


# ---------------------------------------------------------------- a picture of a problem: read once, then it is only text
MAX_IMAGE_B64 = 2_200_000        # the page shrinks a picture to about 1,100 px first, so this is far above what it normally sends


def read_image(body):
    """Turn a picture of a problem into plain text with ONE short call (no animation guide, no chat history). The picture is not kept
    and is never sent again: the user checks the text and sends that."""
    data = str(body.get("image") or "")
    if data.startswith("data:"):
        data = data.split(",", 1)[-1]
    media = "image/png" if body.get("media_type") == "image/png" else "image/jpeg"
    if not data or len(data) > MAX_IMAGE_B64:
        return {"error": "That picture is too large. Try a smaller one."}, 400
    try:
        base64.b64decode(data[:200] + "=" * (-len(data[:200]) % 4))
    except Exception:
        return {"error": "That is not a picture Manimo can read."}, 400
    cfg = load_settings()
    if cfg["provider"] == "anthropic" and not api_key(cfg):
        return {"error": "Add your API key in AI settings first."}, 400
    with _lock:
        if _job.get("state") == "running":
            return {"error": "The assistant is busy. Try again when it finishes."}, 409
    _cancel.clear()
    buf = []
    messages = [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                                             {"type": "text", "text": "Write down the problem in this picture."}]}]
    try:
        stream(cfg, READ_SYSTEM, messages, buf.append, 900)
    except Cancelled:
        return {"error": "Stopped."}, 200
    except AIError as e:
        return {"error": str(e)}, 502
    text = "".join(buf).strip()
    if not text:
        return {"error": "Nothing could be read from that picture."}, 502
    return {"text": text[:6000]}, 200


def estimate(body):
    """About how many tokens the next request will send, so the user can see the cost before pressing Send. (Characters / 4: a guide, not a bill.)"""
    engine = "manim" if body.get("engine") == "manim" else "manimgx"
    prompt = str(body.get("prompt") or "")
    history = [m for m in (body.get("history") or []) if m.get("role") in ("user", "assistant")][-6:]
    mode = body.get("mode") or "write"
    req = {"prompt": prompt, "solve_first": body.get("solve_first"), "mode": mode}
    solve = wants_solve_first(req, mode)
    recent = " ".join([prompt] + [str(m.get("text", "")) for m in history if m.get("role") == "user"])
    guide = len(solve_prompt()) if solve else len(skill_prompt(engine, recent))
    yours = len(prompt) + sum(len(str(m.get("text", ""))) for m in history) + (0 if solve or not body.get("use_code") else len(str(body.get("code") or "")))
    return {"tokens": (guide + yours) // 4, "guide_tokens": guide // 4, "your_tokens": yours // 4, "solve_first": solve,
            "rounds": 1 if solve else MAX_ROUNDS, "output_max": 2200 if solve else MAX_TOKENS}, 200


# ---------------------------------------------------------------- checking the user's own code before it is rendered
def quick_check(code):
    """Fast checks with no render, for code the user pasted or typed: syntax, a Scene to render, names that do not exist,
    the engine's import, and the safety scan. Returns {"engine", "scenes", "issues": [{kind, line, text}]}."""
    code = code or ""
    engine = "manim" if re.search(r"^\s*(?:from|import)\s+manim\b", code, re.M) and not re.search(r"^\s*(?:from|import)\s+manimgx\b", code, re.M) else "manimgx"
    out = {"engine": engine, "scenes": [], "issues": []}
    if not code.strip():
        return out
    try:
        compile(code, "scene.py", "exec")
    except SyntaxError as e:
        out["issues"].append({"kind": "error", "line": e.lineno or None, "text": f"Python cannot read this: {e.msg}" + (f" (column {e.offset})" if e.offset else "")})
        return out
    out["scenes"] = find_scenes(code)
    if not out["scenes"]:
        out["issues"].append({"kind": "error", "line": None, "text": "No scene to render: the code needs a class that extends Scene (or ThreeDScene) with a construct method."})
    if engine == "manimgx":
        if re.search(r"\bm\.[A-Za-z_]", code) and not re.search(r"^\s*import\s+manimgx\s+as\s+m\b", code, re.M):
            out["issues"].append({"kind": "error", "line": 1, "text": "The code uses `m.` but does not start with `import manimgx as m`."})
        if re.search(r"^\s*from\s+manimgx\s+import\s+\*", code, re.M):
            out["issues"].append({"kind": "error", "line": None, "text": "ManimGX code should use `import manimgx as m` and write `m.Circle`, not `from manimgx import *`."})
        out["issues"] += check_names(code)
    for cls in re.finditer(r"^class\s+(\w+)\s*\(([^)]*)\)\s*:", code, re.M):
        if cls.group(1) in out["scenes"]:
            body = code[cls.end():]
            nxt = re.search(r"^class\s", body, re.M)
            if not re.search(r"^\s+def\s+construct\s*\(", body[:nxt.start()] if nxt else body, re.M):
                out["issues"].append({"kind": "error", "line": code[:cls.start()].count("\n") + 1, "text": f"Scene {cls.group(1)} has no `def construct(self)`, so there is nothing to render."})
    out["issues"] += scan_code(code)
    return out


def deep_check(code, scene=None):
    """The same check the assistant uses on its own code: ManimGX `inspect` runs the scene and reports errors with their line and layout
    problems (overlapping text, content outside the frame). Takes a few seconds; Manim CE gets a syntax check only."""
    quick = quick_check(code)
    if any(i["kind"] in ("error", "safety", "name") for i in quick["issues"]) or not quick["scenes"]:
        return {"engine": quick["engine"], "issues": quick["issues"], "scenes": quick["scenes"], "deep": False}
    if quick["engine"] != "manimgx":
        return {"engine": "manim", "issues": quick["issues"], "scenes": quick["scenes"], "deep": False,
                "note": "Manim Community Edition code is checked for syntax here. Render once to find the rest."}
    workdir = Path(tempfile.mkdtemp(prefix="manimo-check-"))
    try:
        scenes = [scene] if scene in quick["scenes"] else quick["scenes"][-1:]
        report = verify_manimgx(code, workdir, scenes)
    except Cancelled:
        return {"engine": "manimgx", "issues": quick["issues"], "scenes": quick["scenes"], "deep": False}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    issues = list(quick["issues"])
    if report.get("error"):
        issues.append({"kind": "error", "line": report["error"].get("line"), "text": report["error"]["text"]})
    for pr in report.get("problems", []):
        issues.append({"kind": "layout", "line": pr.get("line"), "text": pr["text"] + (f" (at {pr['t']})" if pr.get("t") else "")})
    return {"engine": "manimgx", "issues": issues, "scenes": quick["scenes"], "deep": True, "seconds": (report.get("scenes") or [{}])[0].get("seconds")}


def handle(method, path, body):
    """Routes used by server.py. Returns (payload, status)."""
    if method == "POST" and path == "/api/ai/read-image":
        return read_image(body)
    if method == "POST" and path == "/api/ai/estimate":
        return estimate(body)
    if method == "POST" and path == "/api/ai/check":
        code = str(body.get("code") or "")[:400_000]
        if body.get("deep"):
            return deep_check(code, body.get("scene")), 200
        return quick_check(code), 200
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
