"""Imports that Manimo's Python does not have yet: find them in the user's code, name the package to install, and install it on request.

Safety rules (an install runs someone else's code):
  - the package to install is worked out here from the code's imports; the page never sends a package name;
  - wheels only (--only-binary), so no package's build script runs during the install;
  - the user presses Install, and a name that is not on Manimo's short list of known libraries gets a warning and a second confirmation."""
import ast
import importlib
import importlib.util
import os
import re
import subprocess
import sys
import threading

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# Names that are part of the animation tools themselves
OWN = {"manimgx", "manim"}

# import name -> the name on PyPI, where they differ
PIP_NAMES = {"cv2": "opencv-python", "PIL": "pillow", "sklearn": "scikit-learn", "skimage": "scikit-image", "yaml": "pyyaml", "bs4": "beautifulsoup4",
             "dateutil": "python-dateutil", "OpenGL": "PyOpenGL", "Bio": "biopython", "serial": "pyserial", "docx": "python-docx", "fitz": "pymupdf",
             "attr": "attrs", "dotenv": "python-dotenv", "git": "gitpython", "mpl_toolkits": "matplotlib", "pydot": "pydot", "jwt": "pyjwt"}

# Well-known maths, science and drawing libraries that animations commonly use. These get a plain Install button.
KNOWN = {"scipy", "sympy", "mpmath", "matplotlib", "networkx", "pandas", "PIL", "shapely", "skimage", "sklearn", "seaborn", "statsmodels", "numba",
         "svgelements", "svgpathtools", "pygments", "tqdm", "cv2", "trimesh", "pyvista", "galois", "control", "uncertainties", "pint"}


def stdlib():
    return set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}


def package_for(module):
    return PIP_NAMES.get(module, module.replace("_", "-"))


def installed(module):
    try:
        importlib.invalidate_caches()
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def imports(code):
    """Top-level module names the code imports, in order, without repeats. Relative imports and syntax errors give nothing."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []
    seen = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names = [node.module]
        for n in names:
            top = n.split(".")[0]
            if top and top not in seen:
                seen.append(top)
    return seen


def line_of(code, module):
    for i, ln in enumerate((code or "").splitlines(), 1):
        if re.match(rf"\s*(?:import|from)\s+{re.escape(module)}\b", ln):
            return i
    return None


def scan(code):
    """Third-party imports in the code: [{"module", "package", "known", "installed", "line"}]. The standard library and the animation tools are left out."""
    std = stdlib()
    out = []
    for top in imports(code):
        if top in std or top in OWN:
            continue
        out.append({"module": top, "package": package_for(top), "known": top in KNOWN, "installed": installed(top), "line": line_of(code, top)})
    return out


def missing(code):
    return [p for p in scan(code) if not p["installed"]]


def available_known():
    """Known libraries that are installed right now (the assistant may use these)."""
    return sorted(m for m in KNOWN if installed(m))


# ---------------------------------------------------------------- the install job
_lock = threading.Lock()
_job = {"state": "idle", "packages": [], "log": [], "step": "", "error": None}


def state():
    with _lock:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in _job.items()}


def _run(packages):
    cmd = [sys.executable, "-m", "pip", "install", "--only-binary", ":all:", "--disable-pip-version-check", "--progress-bar", "off",
           "--retries", "5", "--timeout", "25"] + packages
    code = 1
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        for raw in iter(proc.stdout.readline, b""):
            line = ANSI.sub("", raw.decode("utf-8", "replace")).strip()
            if line:
                with _lock:
                    _job["log"].append(line)
                    del _job["log"][:-120]
                    _job["step"] = line[:110]
        code = proc.wait()
    except Exception as exc:
        with _lock:
            _job["log"].append(repr(exc))
    importlib.invalidate_caches()
    with _lock:
        if code == 0:
            _job["state"] = "done"
        else:
            tail = " ".join(_job["log"][-6:]).lower()
            _job["state"] = "error"
            if "no matching distribution" in tail or "no versions" in tail:
                _job["error"] = "No ready-made version of that package was found for this Python. Check the name, or ask for a different approach."
            else:
                _job["error"] = "Could not download it. Check your internet connection and try again."


def start(body):
    """Install the packages the given code is missing. `only` may name a subset of those; anything else is refused."""
    code = str(body.get("code") or "")[:400_000]
    want = missing(code)
    only = body.get("only")
    if isinstance(only, list):
        want = [p for p in want if p["module"] in only]
    if not want:
        return {"error": "Nothing to install: every package this code imports is already here."}, 400
    unknown = [p for p in want if not p["known"]]
    if unknown and not body.get("confirm_unknown"):
        return {"error": "That package is not on Manimo's list of known libraries. Confirm to install it anyway.", "needs_confirm": [p["package"] for p in unknown]}, 409
    names = [p["package"] for p in want]
    if not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}", n) for n in names):
        return {"error": "That package name is not valid."}, 400
    with _lock:
        if _job["state"] == "running":
            return {"error": "An install is already running."}, 409
        _job.clear()
        _job.update({"state": "running", "packages": names, "log": [], "step": "Downloading " + ", ".join(names) + "...", "error": None})
    threading.Thread(target=_run, args=(names,), daemon=True).start()
    return {"ok": True, "packages": names}, 200
