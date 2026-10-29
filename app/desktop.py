#!/usr/bin/env python3
"""Manimo desktop window.

A real application window (Microsoft WebView2, through pywebview) around the local Manimo server, so it has its own
title bar, its own taskbar icon and its own place in Alt+Tab. If the native window cannot start (for example the
WebView2 runtime is missing), it falls back to a chromeless Edge/Chrome app window.
"""
import ctypes
import os
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen

import server

AUMID = "Manimo.App"            # must match the shortcut's AppUserModelID so the taskbar shows Manimo's icon
APP_DIR = Path(__file__).resolve().parent


def find_icon():
    for p in (APP_DIR.parent / "manimo.ico", APP_DIR / "manimo.ico", APP_DIR.parent / "installer" / "art" / "manimo.ico"):
        if p.exists():
            return str(p)
    return None


def data_dir():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    d = Path(base) / "Manimo" / "webview"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def log(message):
    """A tiny log next to the window's data, for support (what failed, and why)."""
    try:
        with open(os.path.join(data_dir(), "desktop.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + str(message) + "\n")
    except Exception:
        pass


def windows_setup():
    """Crisp text on scaled displays, and the taskbar identity."""
    if os.name != "nt":
        return 1.0, None
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # per-monitor aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(AUMID)
    except Exception:
        pass
    try:
        from ctypes import wintypes
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rect), 0)   # SPI_GETWORKAREA
        scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100.0 or 1.0
        return scale, ((rect.right - rect.left) / scale, (rect.bottom - rect.top) / scale)
    except Exception:
        return 1.0, None


def fallback(httpd, url):
    server.open_window(url)
    try:
        httpd.serve_forever()
    finally:
        server.stop_running_job()


def project_arg():
    """A project.mo (or its folder) that Windows passed when the user double-clicked it."""
    for a in sys.argv[1:]:
        if a.lower().endswith(".mo") or (os.path.isdir(a) and os.path.isfile(os.path.join(a, "project.mo"))):
            return a
    return None


def main():
    from urllib.parse import quote
    force_browser = "--browser" in sys.argv
    proj = project_arg()
    existing = server.find_running_instance()
    if existing:                                  # already running: bring its window forward, and open the project there
        try:
            urlopen(f"http://127.0.0.1:{existing}/api/focus" + (f"?project={quote(proj)}" if proj else ""), timeout=2).read()
        except Exception:
            pass
        return

    scale, work = windows_setup()
    httpd = server.create_server()
    if httpd is None:
        sys.exit("Manimo could not find a free local port.")
    url = f"http://127.0.0.1:{httpd.server_address[1]}/" + (f"?project={quote(proj)}" if proj else "")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    if force_browser:
        return fallback(httpd, url)
    try:
        import webview
    except Exception:
        return fallback(httpd, url)

    # fit the window inside the usable screen, whatever its size or scaling
    width, height = 1360, 880
    if work:
        width, height = int(min(width, work[0] * 0.95)), int(min(height, work[1] * 0.94))
    min_w, min_h = min(900, width), min(540, height)
    pos = {}
    if work:                                      # centre it inside the usable screen (clear of the taskbar)
        pos = {"x": max(0, int((work[0] - width) / 2)), "y": max(0, int((work[1] - height) / 2))}
    window = webview.create_window("Manimo", url, width=width, height=height, min_size=(min_w, min_h),
                                   background_color="#0e1322", text_select=True, **pos)

    server.HOOKS["quit"].append(lambda: window.destroy())

    def focus():
        try:
            window.restore()
            window.show()
            window.on_top = True
            window.on_top = False
        except Exception:
            pass
    server.HOOKS["focus"].append(focus)

    icon = find_icon()

    def after_start(win):
        try:
            import media_permission
            threading.Thread(target=media_permission.install, args=(win, log), daemon=True).start()
        except Exception as exc:
            log(f"media permission setup failed: {exc!r}")
        if not icon:
            return
        last = None
        for _ in range(60):                        # the form is created a moment after start; wait for it
            try:
                import clr  # noqa: F401  (makes the .NET namespaces importable)
                form = win.native
                if form is not None and form.IsHandleCreated:
                    from System import Action
                    from System.Drawing import Icon
                    ico = Icon(icon)
                    form.Invoke(Action(lambda: setattr(form, "Icon", ico)))   # title bar + taskbar icon
                    log(f"icon set; window state {form.WindowState}, size {form.Width}x{form.Height}")
                    return
            except Exception as exc:
                last = exc
            time.sleep(0.25)
        log(f"could not set the window icon: {last!r}")

    try:
        webview.start(after_start, window, gui="edgechromium", storage_path=data_dir(), private_mode=False)
    except Exception:
        return fallback(httpd, url)
    finally:
        server.stop_running_job()
    os._exit(0)


if __name__ == "__main__":
    main()
