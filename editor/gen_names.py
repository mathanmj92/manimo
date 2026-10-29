"""Writes names.json: what the editor offers when you type `m.`, `self.` or `circle.`.
Re-run after upgrading manimgx:  python gen_names.py"""
import inspect, json, re, sys
from pathlib import Path
import manimgx as m


def first_line(obj):
    doc = inspect.getdoc(obj) or ""
    line = doc.strip().split("\n")[0].strip()
    return line[:140]


def short_default(v):
    if v is inspect.Parameter.empty:
        return None
    r = repr(v)
    r = re.sub(r"\s+", " ", r)
    return r if len(r) <= 14 else "..."


def signature(obj, drop_self=False):
    try:
        sig = inspect.signature(obj.__init__ if inspect.isclass(obj) else obj)
    except (TypeError, ValueError):
        return ""
    parts = []
    for i, p in enumerate(sig.parameters.values()):
        if (drop_self or inspect.isclass(obj)) and i == 0 and p.name in ("self", "cls"):
            continue
        if p.kind is p.VAR_POSITIONAL:
            parts.append("*" + p.name)
        elif p.kind is p.VAR_KEYWORD:
            parts.append("**" + p.name)
        else:
            d = short_default(p.default)
            parts.append(p.name if d is None else f"{p.name}={d}")
    text = ", ".join(parts)
    return text if len(text) <= 150 else text[:147] + "..."


top = []
for name in sorted(n for n in dir(m) if not n.startswith("_")):
    obj = getattr(m, name)
    if inspect.ismodule(obj):
        continue
    if inspect.isclass(obj):
        kind = "class"
    elif callable(obj):
        kind = "function"
    elif name.isupper():
        kind = "constant"
    else:
        kind = "variable"
    entry = {"n": name, "k": kind}
    d = first_line(obj) if kind in ("class", "function") else ""
    if d:
        entry["d"] = d
    if kind in ("class", "function"):
        s = signature(obj)
        if s:
            entry["s"] = s
    top.append(entry)


def methods(cls):
    out = []
    for name in sorted(n for n in dir(cls) if not n.startswith("_")):
        attr = getattr(cls, name, None)
        if attr is None:
            continue
        entry = {"n": name, "k": "method" if callable(attr) else "property"}
        d = first_line(attr)
        if d:
            entry["d"] = d
        if callable(attr):
            s = signature(attr, drop_self=True)
            if s:
                entry["s"] = s
        out.append(entry)
    return out


scene = methods(m.Scene)
mob = {e["n"]: e for e in methods(m.Mobject)}
for e in methods(m.VMobject):
    mob.setdefault(e["n"], e)
modules = sorted(n for n in dir(m) if not n.startswith("_") and inspect.ismodule(getattr(m, n)))
data = {"version": __import__("importlib.metadata", fromlist=["version"]).version("manimgx"),
        "top": top, "scene": scene, "mobject": sorted(mob.values(), key=lambda e: e["n"])}
Path(__file__).with_name("names.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
# the AI assistant checks generated code against these names, so ship a compact copy beside the app
ai_dir = Path(__file__).resolve().parent.parent / "app" / "ai"
ai_dir.mkdir(parents=True, exist_ok=True)
(ai_dir / "names.json").write_text(json.dumps({
    "version": data["version"], "top": [e["n"] + ":" + e["k"] for e in top], "modules": modules,
    "scene": [e["n"] for e in scene], "mobject": [e["n"] for e in data["mobject"]]}, separators=(",", ":")), encoding="utf-8")
print(f"{len(top)} names, {len(scene)} scene members, {len(mob)} mobject members")
