"""Scene operations on a code file, for the Storyboard: list the scenes, reorder, duplicate, delete, rename, add one from a template,
and read an assistant plan into cards. All of it works on the text of the file and never runs it. Every result is checked to still compile."""
import ast
import hashlib
import io
import keyword
import re
import tokenize

SCENE_BASE = re.compile(r"(^|\.)\w*Scene\w*$")
SAY_SPAN = re.compile(r"[\[\]]")


class SceneError(Exception):
    pass


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _tree(code):
    try:
        return ast.parse(code)
    except SyntaxError as e:
        raise SceneError(f"The code has a syntax error on line {e.lineno or '?'}, so the scenes cannot be moved yet: {e.msg}.") from None


def blocks(code):
    """The scene classes at the top level of the file, in order: name, the lines they occupy (start..end, end exclusive), and what is in them."""
    lines = code.split("\n")
    out = []
    for node in _tree(code).body:
        if not isinstance(node, ast.ClassDef) or not any(SCENE_BASE.search(_dotted(b)) for b in node.bases):
            continue
        start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
        while start > 0 and lines[start - 1].lstrip().startswith("#"):      # a comment right above the class travels with it
            start -= 1
        words = plays = 0
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                if sub.func.attr == "say" and sub.args and isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str):
                    words += len(SAY_SPAN.sub("", sub.args[0].value).split())
                elif sub.func.attr == "play":
                    plays += 1
        text = "\n".join(lines[start:node.end_lineno])
        out.append({"name": node.name, "start": start, "end": node.end_lineno, "line": node.lineno, "words": words, "plays": plays,
                    "hash": hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]})
    return out


def info(code):
    """What a card shows. `seconds` is an estimate from the narration (about 2.6 words a second) or, without narration, from the animations."""
    res = []
    for b in blocks(code):
        est = b["words"] / 2.6 + 0.6 * b["plays"] if b["words"] else 1.2 * b["plays"]
        res.append({"name": b["name"], "start": b["start"] + 1, "line": b["line"], "end": b["end"], "words": b["words"], "plays": b["plays"], "est_seconds": round(est, 1), "hash": b["hash"]})
    return res


def _finish(code):
    _tree(code)                                  # never hand back code that no longer compiles
    return code


def _rename_in(text, old, new):
    """Rename a name in Python text without touching strings or comments (only NAME tokens change)."""
    lines = text.split("\n")
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError):
        raise SceneError("Could not read that scene to rename it.") from None
    for tok in reversed(toks):
        if tok.type == tokenize.NAME and tok.string == old:
            (r, c), (_, c2) = tok.start, tok.end
            lines[r - 1] = lines[r - 1][:c] + new + lines[r - 1][c2:]
    return "\n".join(lines)


def _unique(name, taken):
    n = 2
    base = re.sub(r"_\d+$", "", name)
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


def _check_name(new, taken):
    if not new.isidentifier() or keyword.iskeyword(new):
        raise SceneError("A scene name uses letters, numbers and underscores, and cannot start with a number.")
    if new in taken:
        raise SceneError(f"There is already a scene called {new}.")


def _parts(code):
    """The file as gap, scene, gap, scene ... gap (each a list of lines), so scenes can change places while imports and helpers stay put."""
    bl = blocks(code)
    lines = code.split("\n")
    gaps, texts, pos = [], [], 0
    for b in bl:
        gaps.append(lines[pos:b["start"]])
        texts.append(lines[b["start"]:b["end"]])
        pos = b["end"]
    gaps.append(lines[pos:])
    return bl, gaps, texts


def _assemble(gaps, texts):
    out = list(gaps[0])
    for i, t in enumerate(texts):
        gap = gaps[i + 1]
        if 0 < i + 1 < len(texts) and not any(ln.strip() for ln in gap):
            gap = ["", ""]                      # two scenes next to each other always get two blank lines, whatever order they are in
        out += t + gap
    return "\n".join(out)


def reorder(code, order):
    bl, gaps, texts = _parts(code)
    names = [b["name"] for b in bl]
    if sorted(order) != sorted(names) or len(set(order)) != len(order):
        raise SceneError("The new order must list every scene once.")
    by = dict(zip(names, texts))
    return _finish(_assemble(gaps, [by[n] for n in order]))


def duplicate(code, name):
    """A copy right after the original, named Name_2 (or the next free number). Returns (code, the new name)."""
    bl, gaps, texts = _parts(code)
    names = [b["name"] for b in bl]
    if name not in names:
        raise SceneError(f"There is no scene called {name}.")
    i = names.index(name)
    new = _unique(name, set(names))
    copy = _rename_in("\n".join(texts[i]), name, new).split("\n")
    texts2 = texts[:i + 1] + [copy] + texts[i + 1:]
    gaps2 = gaps[:i + 1] + [["", ""]] + gaps[i + 1:]            # two blank lines between the original and its copy
    return _finish(_assemble(gaps2, texts2)), new


def delete(code, name):
    bl, gaps, texts = _parts(code)
    names = [b["name"] for b in bl]
    if name not in names:
        raise SceneError(f"There is no scene called {name}.")
    if len(names) == 1:
        raise SceneError("That is the only scene. Add another one first, or clear the editor instead.")
    i = names.index(name)
    merged = _merge(gaps[i], gaps[i + 1], first=i == 0, last=i == len(names) - 1)      # whatever sat around the scene (helpers, comments) stays
    gaps2 = gaps[:i] + [merged] + gaps[i + 2:]
    texts2 = texts[:i] + texts[i + 1:]
    return _finish(_assemble(gaps2, texts2))


def _merge(a, b, first, last):
    """The gap before a removed scene (a) and the gap after it (b) become one gap."""
    def trim_end(x):
        x = list(x)
        while x and not x[-1].strip():
            x.pop()
        return x

    def trim_start(x):
        x = list(x)
        while x and not x[0].strip():
            x.pop(0)
        return x
    ca, cb = any(ln.strip() for ln in a), any(ln.strip() for ln in b)
    if ca and cb:
        return trim_end(a) + ["", ""] + trim_start(b)
    if ca:
        return trim_end(a) + (list(b) if last else ["", ""])
    if cb:
        return (trim_start(b) if first else ["", ""] + trim_start(b))
    return list(b) if last else ["", ""]


def _imports(code):
    """The import lines at the top level of a file, in order, without repeats."""
    out = []
    for node in _tree(code).body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            line = ast.get_source_segment(code, node)
            if line and line not in out:
                out.append(line)
    return out


def replace(code, name, other):
    """Put the scene `name` from another version of the file (`other`, for example one of the assistant's takes) in its place here.
    Imports that the other version added are added too; nothing else in this file changes."""
    here = {b["name"]: b for b in blocks(code)}
    there = {b["name"]: b for b in blocks(other)}
    if name not in here:
        raise SceneError(f"There is no scene called {name} in your code.")
    if name not in there:
        raise SceneError(f"That take has no scene called {name}.")
    _, gaps, texts = _parts(code)
    names = [b["name"] for b in blocks(code)]
    o_lines = other.split("\n")
    take = o_lines[there[name]["start"]:there[name]["end"]]
    texts[names.index(name)] = take
    new = _assemble(gaps, texts)
    missing = [ln for ln in _imports(other) if ln not in _imports(new)]
    if missing:
        rows = new.split("\n")
        last = max((n.end_lineno for n in _tree(new).body if isinstance(n, (ast.Import, ast.ImportFrom))), default=0)
        rows[last:last] = missing                                  # straight after the existing imports (or at the top when there are none)
        new = "\n".join(rows)
    return _finish(new)


def rename(code, old, new):
    names = [b["name"] for b in blocks(code)]
    if old not in names:
        raise SceneError(f"There is no scene called {old}.")
    if new == old:
        return code
    _check_name(new, set(names))
    return _finish(_rename_in(code, old, new))


# ---------------------------------------------------------------- templates for "add a scene"
TEMPLATES = {
    "title": ("Title", "Title card", "A title and one line that says what the video is about."),
    "equation": ("Equation", "Equation, step by step", "An equation that builds up, with the key part highlighted."),
    "graph": ("Graph", "Graph of a function", "Axes with a curve drawn on them."),
    "compare": ("Compare", "Side by side", "Two ideas next to each other."),
    "summary": ("Summary", "Summary list", "Key points that appear one at a time."),
}


def template_list():
    return [{"id": k, "label": v[1], "about": v[2]} for k, v in TEMPLATES.items()]


def _engine(code):
    if re.search(r"^\s*(?:from|import)\s+manimgx\b", code, re.M):
        return "manimgx"
    if re.search(r"^\s*(?:from|import)\s+manim\b", code, re.M):
        return "manim"
    return "manimgx"


def template_code(kind, name, engine):
    """The new scene's code. ManimGX scenes get a spoken line (`self.say`), which Manimo reads aloud offline; Manim CE scenes are silent."""
    P = "m." if engine == "manimgx" else ""
    base = f"{P}Scene"

    def say(text, anim):
        return f'self.say("{text}", {anim})' if engine == "manimgx" else f"self.play({anim})"
    head = f"class {name}({base}):\n    def construct(self):\n"
    if kind == "title":
        body = (f'        title = {P}Text("Your title", font_size=56)\n'
                f'        sub = {P}Text("One line that says what this video is about", font_size=30, color={P}GREY_B).next_to(title, {P}DOWN)\n'
                f'        {say("Welcome. In this video we will look at one idea.", f"{P}Write(title)")}\n'
                f'        self.play({P}FadeIn(sub))\n        self.wait(1)\n        self.play({P}FadeOut({P}VGroup(title, sub)))\n')
    elif kind == "equation":
        body = (f'        eq = {P}MathTex("a^2 + b^2 = c^2", font_size=64)\n'
                f'        box = {P}SurroundingRectangle(eq, color={P}YELLOW, buff=0.3)\n'
                f'        {say("Here is the equation.", f"{P}Write(eq)")}\n'
                f'        {say("The two squares on the left add up to the square on the right.", f"{P}Create(box)")}\n'
                f'        self.wait(1)\n        self.play({P}FadeOut({P}VGroup(eq, box)))\n')
    elif kind == "graph":
        body = (f'        axes = {P}Axes(x_range=[0, 6, 1], y_range=[0, 4, 1], x_length=7, y_length=4)\n'
                f'        curve = axes.plot(lambda x: 0.1 * x * x, color={P}BLUE)\n'
                f'        label = {P}Text("y = 0.1 x squared", font_size=30).next_to(axes, {P}UP)\n'
                f'        {say("These are the axes.", f"{P}Create(axes)")}\n'
                f'        {say("And this curve shows how y grows with x.", f"{P}Create(curve)")}\n'
                f'        self.play({P}FadeIn(label))\n        self.wait(1)\n        self.play({P}FadeOut({P}VGroup(axes, curve, label)))\n')
    elif kind == "compare":
        body = (f'        left = {P}Text("First idea", font_size=40, color={P}BLUE).move_to({P}LEFT * 3 + {P}UP * 2)\n'
                f'        right = {P}Text("Second idea", font_size=40, color={P}ORANGE).move_to({P}RIGHT * 3 + {P}UP * 2)\n'
                f'        divider = {P}Line({P}UP * 2.5, {P}DOWN * 3, color={P}GREY_B)\n'
                f'        {say("Here are two ideas side by side.", f"{P}AnimationGroup({P}Write(left), {P}Write(right), {P}Create(divider))")}\n'
                f'        self.wait(1)\n        self.play({P}FadeOut({P}VGroup(left, right, divider)))\n')
    elif kind == "summary":
        body = (f'        title = {P}Text("In short", font_size=48).to_edge({P}UP)\n'
                f'        points = {P}VGroup(*[{P}Text(t, font_size=34) for t in ["First key point", "Second key point", "Third key point"]]).arrange({P}DOWN, aligned_edge={P}LEFT, buff=0.5)\n'
                f'        {say("Let us sum up.", f"{P}Write(title)")}\n'
                f'        for p in points:\n            self.play({P}FadeIn(p))\n        self.wait(1)\n        self.play({P}FadeOut({P}VGroup(title, points)))\n')
    else:
        raise SceneError("Unknown scene template.")
    return head + body


def add_template(code, kind, name=None):
    if kind not in TEMPLATES:
        raise SceneError("Unknown scene template.")
    names = {b["name"] for b in blocks(code)} if code.strip() else set()
    name = name or _next_name(TEMPLATES[kind][0], names)
    _check_name(name, names)
    engine = _engine(code)
    new = template_code(kind, name, engine)
    if not code.strip():
        head = "import manimgx as m\n\n\n" if engine == "manimgx" else "from manim import *\n\n\n"
        return _finish(head + new), name
    return _finish(code.rstrip("\n") + "\n\n\n" + new), name


def _next_name(base, taken):
    if base not in taken:
        return base
    n = 2
    while f"{base}{n}" in taken:
        n += 1
    return f"{base}{n}"


# ---------------------------------------------------------------- reading the assistant's plan
def parse_plan(text):
    """The assistant's plan (Title / For / Look / numbered scenes with 'Narration:') as {title, audience, look, scenes: [{name, sees, narration}]}."""
    text = text or ""
    out = {"title": "", "audience": "", "look": "", "scenes": [], "check": ""}
    for key, label in (("title", "Title"), ("audience", "For"), ("look", "Look"), ("check", "Check")):
        m = re.search(rf"^\s*\**{label}\**\s*:\s*(.+)$", text, re.M | re.I)
        if m:
            out[key] = m.group(1).strip().strip("*").strip()
    for m in re.finditer(r"^\s*(\d{1,2})[.)]\s+(.+?)(?=^\s*\d{1,2}[.)]\s|^\s*\**Check\**\s*:|\Z)", text, re.M | re.S):
        body = " ".join(m.group(2).split())
        narr = re.search(r"\bNarration\s*:\s*(.*)$", body, re.I)
        sees = body[:narr.start()].strip() if narr else body
        head = re.match(r"\**(.+?)\**\s+[-–—:]\s+(.*)$", sees)
        name, what = (head.group(1).strip(), head.group(2).strip()) if head else (sees.split(".")[0][:40].strip(), sees)
        out["scenes"].append({"name": name.strip("*").strip(), "sees": what.rstrip(" ."), "narration": (narr.group(1).strip() if narr else "")})
    return out


def class_name(label, taken=()):
    """A safe class name from a scene's label: 'The circuit' becomes TheCircuit."""
    words = re.findall(r"[A-Za-z0-9]+", label or "")
    name = "".join(w[:1].upper() + w[1:] for w in words)[:40] or "Scene"
    if name[0].isdigit():
        name = "Scene" + name
    if keyword.iskeyword(name):
        name += "_"
    return _next_name(name, set(taken))
