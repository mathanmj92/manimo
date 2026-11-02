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


_keep = []   # the window procedure must stay alive as long as the window does


def hide_title_bar(form, log):
    """Take Windows' own title bar away and keep everything else (resize edges, snap, shadow), so Manimo's top bar is the only one."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallWindowProcW.restype = LRESULT
    hwnd = wintypes.HWND(form.Handle.ToInt64())
    old = {}

    def proc(h, msg, wparam, lparam):
        if msg == 0x0083 and wparam:                         # WM_NCCALCSIZE: let Windows lay out the borders, then give the title bar's height back
            rect = ctypes.cast(lparam, ctypes.POINTER(wintypes.RECT))
            top = rect[0].top
            res = user32.CallWindowProcW(old["proc"], h, msg, wparam, lparam)
            rect[0].top = top
            return res
        return user32.CallWindowProcW(old["proc"], h, msg, wparam, lparam)

    cb = WNDPROC(proc)
    _keep.append(cb)
    old["proc"] = user32.SetWindowLongPtrW(hwnd, -4, ctypes.cast(cb, ctypes.c_void_p))
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x37)        # FRAMECHANGED | NOMOVE | NOSIZE | NOZORDER | NOACTIVATE
    return hwnd


def window_actions(form, hwnd):
    import ctypes
    from System import Action
    user32 = ctypes.windll.user32

    def move():
        user32.ReleaseCapture()
        user32.SendMessageW(hwnd, 0x00A1, 2, 0)               # WM_NCLBUTTONDOWN on the caption: Windows runs the move until the button is released

    def do(action):
        if action == "min":
            user32.ShowWindow(hwnd, 6)
        elif action == "max":
            user32.ShowWindow(hwnd, 9 if user32.IsZoomed(hwnd) else 3)
        elif action == "drag":
            form.BeginInvoke(Action(move))                    # on the window's own thread, which is where the mouse is tracked
    return do


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

    def install_chrome(win):
        if "--native-title" in sys.argv:
            return
        for _ in range(60):
            try:
                import clr  # noqa: F401
                form = win.native
                if form is not None and form.IsHandleCreated:
                    from System import Action
                    box = {}
                    form.Invoke(Action(lambda: box.update(hwnd=hide_title_bar(form, log))))
                    do = window_actions(form, box["hwnd"])
                    server.HOOKS["window"].append(lambda a: (log(f"window action {a}"), window.destroy() if a == "close" else do(a)))
                    server.CHROME["custom"] = True
                    log("own title bar buttons on")
                    return
            except Exception as exc:
                log(f"could not hide the title bar: {exc!r}")
                return
            time.sleep(0.25)

    def after_start(win):
        try:
            import media_permission
            threading.Thread(target=media_permission.install, args=(win, log), daemon=True).start()
        except Exception as exc:
            log(f"media permission setup failed: {exc!r}")
        threading.Thread(target=install_chrome, args=(win,), daemon=True).start()
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
