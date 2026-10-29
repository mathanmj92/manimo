"""Lets Manimo's own page use the microphone and camera inside the WebView2 window.

pywebview does not answer WebView2's permission requests, so without this the Narrate recorder cannot reach the
microphone or camera. Only the two media permissions are granted, and only to the local Manimo page (127.0.0.1);
everything else keeps WebView2's default behaviour.
"""
import time


def install(win, log=print, wait=15.0):
    """Hook the permission event once the WebView2 control exists. Returns True when it was installed."""
    last = None
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            import clr  # noqa: F401
            form = win.native
            if form is not None and form.IsHandleCreated:
                from System import Action
                from Microsoft.Web.WebView2.Core import CoreWebView2PermissionKind as Kind, CoreWebView2PermissionState as State
                done = []

                def on_permission(sender, args):
                    try:
                        local = str(args.Uri).startswith(("http://127.0.0.1:", "http://localhost:"))
                        if local and args.PermissionKind in (Kind.Microphone, Kind.Camera):
                            args.State = State.Allow
                            log("allowed %s for the local page" % args.PermissionKind)
                    except Exception as exc:
                        log("permission handler error: %r" % (exc,))

                def hook():        # WebView2 objects may only be touched on the window's own thread
                    core = form.webview.CoreWebView2
                    if core is not None:
                        core.PermissionRequested += on_permission
                        done.append(True)
                form.Invoke(Action(hook))
                if done:
                    log("microphone/camera permission handler installed")
                    return True
        except Exception as exc:
            last = exc
        time.sleep(0.25)
    log("could not install the microphone/camera permission handler: %r" % (last,))
    return False
