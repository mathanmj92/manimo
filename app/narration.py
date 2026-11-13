"""Narration in a code file: the spoken lines (`self.say("...")`), editing them in place, and the speech settings kept as comments in the file
(`# voice:` and `# speed:` above a scene, `# say: written = spoken` for pronunciations). Works on the text; never runs the code."""
import ast
import json
import re

import scenes
import voice

SPAN = re.compile(r"\[[^\]]*\]")
KINDS = ("say", "voiceover")


class NarrationError(Exception):
    pass


def _offsets(code):
    """Absolute start offset of every line, to turn (line, byte column) into a character position."""
    pos, out = 0, [0]
    for ln in code.split("\n"):
        pos += len(ln) + 1
        out.append(pos)
    return out


def _abs(code, starts, lineno, byte_col):
    line = code.split("\n")[lineno - 1]
    return starts[lineno - 1] + len(line.encode("utf-8")[:byte_col].decode("utf-8", "ignore"))


def lines(code):
    """Every spoken line, in file order: scene, its number within the scene, where it is, the raw text (with [brackets]) and where in the text it sits."""
    tree = scenes._tree(code)
    starts, out = _offsets(code), []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not any(scenes.SCENE_BASE.search(scenes._dotted(b)) for b in node.bases):
            continue
        found = []
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            const, kind = None, None
            if isinstance(sub.func, ast.Attribute) and sub.func.attr == "say" and sub.args:
                const, kind = sub.args[0], "say"
            elif isinstance(sub.func, ast.Attribute) and sub.func.attr == "voiceover":
                const, kind = next((k.value for k in sub.keywords if k.arg == "text"), None), "voiceover"
            if isinstance(const, ast.Constant) and isinstance(const.value, str):
                found.append((const.lineno, const.col_offset, sub, const, kind))
        for n, (ln, col, call, const, kind) in enumerate(sorted(found, key=lambda f: (f[0], f[1]))):
            out.append({"scene": node.name, "n": n, "line": ln, "text": const.value, "kind": kind,
                        "animations": len(call.args) - 1 if kind == "say" else 0,
                        "start": _abs(code, starts, const.lineno, const.col_offset), "end": _abs(code, starts, const.end_lineno, const.end_col_offset)})
    return out


def public(code):
    return [{k: v for k, v in l.items() if k not in ("start", "end")} for l in lines(code)]


def _literal(text):
    return json.dumps(text, ensure_ascii=False)          # a double-quoted string with every quote, backslash and newline escaped


def set_lines(code, edits):
    """edits: [{scene, n, text}]. Only the text inside the quotes changes. A line keeps its [bracketed] parts: one for each animation."""
    have = {(l["scene"], l["n"]): l for l in lines(code)}
    todo = []
    for e in edits:
        key = (str(e.get("scene")), int(e.get("n", -1)))
        old = have.get(key)
        if old is None:
            raise NarrationError("That line is no longer in the code.")
        text = " ".join(str(e.get("text", "")).split())
        if not text:
            raise NarrationError("A spoken line cannot be empty. Delete the line in the code instead.")
        if len(SPAN.findall(text)) != len(SPAN.findall(old["text"])):
            n = len(SPAN.findall(old["text"]))
            raise NarrationError(f"Line {old['line']} has {n} [bracketed] {'part' if n == 1 else 'parts'}, one for each animation. Keep the same number of brackets."
                                 if n else f"Line {old['line']} has no [brackets], and its animation plays during the whole line. Keep it without brackets.")
        if text != old["text"]:
            todo.append((old["start"], old["end"], _literal(text)))
    for start, end, lit in sorted(todo, reverse=True):
        code = code[:start] + lit + code[end:]
    return scenes._finish(code)


# ---------------------------------------------------------------- voice and speed above a scene
def scene_settings(code):
    out = {}
    for b in scenes.blocks(code):
        a = voice.annotations(code, b["name"])
        out[b["name"]] = {"voice": a["voice"], "speed": a["speed"]}
    return out


def set_scene_settings(code, scene, voice_id=None, speed=None):
    """Write `# voice:` and `# speed:` in the comment lines above the scene class (None removes the line, so the scene uses the lesson's voice)."""
    bl = [b for b in scenes.blocks(code) if b["name"] == scene]
    if not bl:
        raise NarrationError(f"There is no scene called {scene}.")
    if voice_id and voice_id not in voice.VOICES:
        raise NarrationError("That voice is not one of Manimo's voices.")
    if speed is not None:
        try:
            speed = round(min(1.4, max(0.7, float(speed))), 2)
        except (TypeError, ValueError):
            raise NarrationError("The speed must be a number between 0.7 and 1.4.") from None
    rows = code.split("\n")
    start = bl[0]["start"]
    end = start
    while end < len(rows) and rows[end].lstrip().startswith("#"):
        end += 1
    keep = [r for r in rows[start:end] if not re.match(r"\s*#\s*(voice|speed)\s*:", r, re.I)]
    add = ([f"# voice: {voice_id}"] if voice_id else []) + ([f"# speed: {speed:g}"] if speed is not None else [])
    rows[start:end] = keep + add
    return scenes._finish("\n".join(rows))


# ---------------------------------------------------------------- how words are said, for the whole file
def pronunciations(code):
    a = voice.annotations(code)
    return {"pairs": [list(p) for p in a["pron"]], "defaults": a["defaults"],
            "builtin": [[w, s.strip()] for w, s in voice.BUILTIN_PRON]}


def set_pronunciations(code, pairs, defaults=True):
    clean = []
    for p in pairs or []:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise NarrationError("Each pronunciation needs the written word and how to say it.")
        a, b = " ".join(str(p[0]).split()), " ".join(str(p[1]).split())
        if not a and not b:
            continue
        if not a or not b:
            raise NarrationError("Fill in both the written word and how it is said, or remove the row.")
        if "=" in a or "#" in a:
            raise NarrationError("The written word cannot contain = or #.")
        clean.append((a, b))
    rows = [r for r in code.split("\n") if not voice.SAY_LINE.match(r) and not voice.DEFAULTS_OFF.match(r)]
    while rows and not rows[0].strip():                       # the blank line that followed the old block
        rows.pop(0)
    block = ([] if defaults else ["# say-defaults: off"]) + [f"# say: {a} = {b}" for a, b in clean]
    return scenes._finish("\n".join(block + [""] + rows) if block else "\n".join(rows))
