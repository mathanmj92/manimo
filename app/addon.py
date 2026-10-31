"""The add-on pack: Manim Community Edition and a trimmed LaTeX, downloaded after Manimo is installed.

The lean installer does not carry them. This module fetches `Manimo-CE-LaTeX-Pack-<version>.zip` from the GitHub release of the
installed Manimo version, checks its SHA-256 against the value GitHub publishes, and installs it next to the private Python:
Manim CE and its packages with `pip --no-index` from the pack's own wheels, and the TeX tree into `<install>\\texlive`.
It needs no administrator rights, changes no PATH or registry setting, and the pack is never run, only unpacked.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = "mathanmj92/manimo"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class AddonError(Exception):
    """A problem with a plain-language message for the user."""


class NoPack(AddonError):
    """No pack is published for this version (the caller may fall back to something else)."""


# ---------------------------------------------------------------- pure helpers (unit-tested)
def pack_name(version):
    return f"Manimo-CE-LaTeX-Pack-{str(version).lstrip('v')}.zip"


def find_pack(assets, version):
    for a in assets or []:
        if a.get("name") == pack_name(version):
            return a
    return None


def sha_from_sums(text, name):
    """The hash for `name` in a SHA256SUMS.txt ('<64 hex>  <name>' per line, with or without a '*' before the name)."""
    for line in (text or "").splitlines():
        m = re.match(r"\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*$", line)
        if m and m.group(2) == name:
            return m.group(1).lower()
    return None


def pack_sha256(assets, version, sums_text=""):
    a = find_pack(assets, version)
    if not a:
        return None
    d = str(a.get("digest") or "")
    if d.lower().startswith("sha256:"):
        return d.split(":", 1)[1].strip().lower()
    return sha_from_sums(sums_text, a["name"])


def safe_members(names):
    """Refuse a zip that would write outside the folder it is unpacked into."""
    for n in names:
        p = Path(n.replace("\\", "/"))
        if p.is_absolute() or n.startswith(("/", "\\")) or ".." in p.parts or re.match(r"^[A-Za-z]:", n):
            raise AddonError("The add-on file contains an unsafe path, so it was not used.")
    return list(names)


def install_root():
    """The Manimo folder that holds the private Python (<root>\\python\\python.exe), or None when running some other Python."""
    exe = Path(sys.executable).resolve()
    root = exe.parent.parent
    return root if exe.parent.name.lower() == "python" and (root / "app").is_dir() else None


# ---------------------------------------------------------------- network
def _get(url, timeout=15, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "Manimo-addon"})
    return urllib.request.urlopen(req, timeout=timeout)


def release_info(version, api_base=None):
    """The GitHub release for this exact Manimo version: (pack asset, expected sha256)."""
    base = api_base or f"https://api.github.com/repos/{REPO}"
    try:
        with _get(f"{base}/releases/tags/v{str(version).lstrip('v')}") as r:
            rel = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NoPack("No add-on pack is published for Manimo %s yet." % version)
        raise AddonError("GitHub answered with an error (%s). Try again later." % e.code)
    except Exception as e:
        raise AddonError("Could not reach GitHub. Check your internet connection and try again.")
    assets = rel.get("assets") or []
    a = find_pack(assets, version)
    if not a:
        raise NoPack("The Manimo %s release does not include the Manim CE and LaTeX add-on." % version)
    sums = ""
    s = next((x for x in assets if x.get("name") == "SHA256SUMS.txt"), None)
    if s:
        try:
            with _get(s["browser_download_url"], accept="*/*") as r:
                sums = r.read(200_000).decode("utf-8", "replace")
        except Exception:
            sums = ""
    sha = pack_sha256(assets, version, sums)
    if not sha:
        raise AddonError("The release does not publish a checksum for the add-on, so it was not downloaded.")
    return a, sha


def download(asset, sha, dest, progress, cancelled):
    part = Path(str(dest) + ".part")
    total, done, h = int(asset.get("size") or 0), 0, hashlib.sha256()
    try:
        with _get(asset["browser_download_url"], timeout=30, accept="application/octet-stream") as r, open(part, "wb") as f:
            while True:
                if cancelled():
                    raise AddonError("Cancelled.")
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                progress("Downloading Manim CE and LaTeX... %d of %d MB" % (done >> 20, max(total, done) >> 20), 100.0 * done / total if total else None)
        if total and done != total:
            raise AddonError("The download was cut short. Check your connection and try again.")
        if h.hexdigest().lower() != sha.lower():
            raise AddonError("The downloaded file does not match its published checksum, so it was deleted. Try again.")
        os.replace(part, dest)
    finally:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------- install
def _run(cmd, cwd=None, env=None):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd, env=env,
                       stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, timeout=1800)
    return p.returncode, ((p.stdout or "") + (p.stderr or ""))[-1500:]


def install_pack(zip_path, root, progress):
    """Unpack the zip, install Manim CE from its wheels, put the TeX tree in <root>\\texlive, then prove both start."""
    work = Path(tempfile.mkdtemp(prefix="manimo-addon-"))
    try:
        progress("Unpacking...", None)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(work, members=safe_members(z.namelist()))
        wheels, req = work / "wheels-ce", work / "requirements-ce.txt"
        if not wheels.is_dir() or not req.is_file() or not (work / "texlive" / "bin" / "windows" / "latex.exe").is_file():
            raise AddonError("The add-on file is not complete, so it was not installed.")
        progress("Installing Manim Community Edition...", None)
        code, out = _run([sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(wheels), "-r", str(req),
                          "--disable-pip-version-check", "--progress-bar", "off"])
        if code:
            raise AddonError("Manim could not be installed: " + out.strip().splitlines()[-1][:200] if out.strip() else "Manim could not be installed.")
        progress("Adding LaTeX...", None)
        tex = root / "texlive"
        if tex.exists():
            shutil.rmtree(tex, ignore_errors=True)
        shutil.move(str(work / "texlive"), str(tex))
        progress("Checking that it works...", None)
        code, out = _run([sys.executable, "-c", "import manim; print(manim.__version__)"])
        if code:
            raise AddonError("Manim was installed but cannot start: " + out.strip()[-200:])
        for exe in ("latex.exe", "dvisvgm.exe"):
            code, out = _run([str(tex / "bin" / "windows" / exe), "--version"])
            if code:
                raise AddonError("LaTeX was added but %s cannot start." % exe)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run(version, progress, cancelled, data_dir, api_base=None, root=None):
    """The whole add-on install for `version`. Raises AddonError (or NoPack) with a message fit to show the user."""
    root = root or install_root()
    if not root:
        raise AddonError("This copy of Manimo is not the installed app, so it cannot add the pack.")
    progress("Looking for the add-on...", None)
    asset, sha = release_info(version, api_base)
    folder = Path(data_dir) / "addons"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / asset["name"]
    if not (dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest().lower() == sha):     # reuse an earlier complete download
        download(asset, sha, dest, progress, cancelled)
    install_pack(dest, root, progress)
    try:
        dest.unlink()
    except OSError:
        pass
