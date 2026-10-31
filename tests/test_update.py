"""Update check: version rules, which installer to pick, checksums, and the whole check-download-verify flow
against a small local server that pretends to be GitHub (the real GitHub is never contacted)."""
import hashlib
import http.server
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tests import APP  # noqa: F401  (sets sys.path)
import update


class Helpers(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(update.parse_version("v1.9.10"), (1, 9, 10))
        self.assertIsNone(update.parse_version("1.9"))
        self.assertIsNone(update.parse_version("nightly"))
        self.assertTrue(update.is_newer("v1.9.10", "1.9.9"))      # numbers, not text: 10 is newer than 9
        self.assertTrue(update.is_newer("2.0.0", "1.9.9"))
        self.assertFalse(update.is_newer("1.9.5", "1.9.5"))
        self.assertFalse(update.is_newer("1.9.4", "1.9.5"))
        self.assertFalse(update.is_newer("garbage", "1.9.5"))

    def test_variant_from_marker_and_folder(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "app").mkdir()
            self.assertEqual(update.installer_variant(root / "app"), "lean")
            (root / "texlive").mkdir()
            self.assertEqual(update.installer_variant(root / "app"), "full")     # older installs: told apart by the bundled TeX Live
            (root / "variant.txt").write_text("lean\n", encoding="utf-8")
            self.assertEqual(update.installer_variant(root / "app"), "lean")     # the marker wins
            (root / "variant.txt").write_text("nonsense", encoding="utf-8")
            self.assertEqual(update.installer_variant(root / "app"), "full")

    def test_pick_asset(self):
        assets = [{"name": "Manimo-Setup-1.9.6.exe"}, {"name": "Manimo-Full-Setup-1.9.6.exe"}, {"name": "SHA256SUMS.txt"}]
        self.assertEqual(update.pick_asset(assets, "v1.9.6", "full")["name"], "Manimo-Full-Setup-1.9.6.exe")
        self.assertEqual(update.pick_asset(assets, "1.9.6", "lean")["name"], "Manimo-Setup-1.9.6.exe")
        self.assertEqual(update.pick_asset(assets[:1], "1.9.6", "full")["name"], "Manimo-Setup-1.9.6.exe")   # no full build: the plain one
        self.assertIsNone(update.pick_asset([{"name": "other.zip"}], "1.9.6", "lean"))

    def test_expected_sha256(self):
        h = "a" * 64
        self.assertEqual(update.expected_sha256({"name": "x.exe", "digest": "sha256:" + h.upper()}), h)
        self.assertEqual(update.expected_sha256({"name": "x.exe"}, "Download\n\nSHA-256: " + h), h)
        self.assertEqual(update.expected_sha256({"name": "x.exe"}, "x.exe  " + h), h)
        self.assertIsNone(update.expected_sha256({"name": "x.exe"}, "no checksum here"))


class FakeGitHub(http.server.BaseHTTPRequestHandler):
    payload = b"MZ" + bytes(range(256)) * 400          # a stand-in for an installer
    bad = False

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/release":
            port = self.server.server_address[1]
            data = FakeGitHub.payload if not FakeGitHub.bad else FakeGitHub.payload[:-1] + b"X"
            body = json.dumps({"tag_name": "v9.9.9", "body": "Notes", "assets": [{
                "name": "Manimo-Setup-9.9.9.exe", "size": len(FakeGitHub.payload), "browser_download_url": f"http://127.0.0.1:{port}/file",
                "digest": "sha256:" + hashlib.sha256(FakeGitHub.payload).hexdigest()}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/file":
            data = FakeGitHub.payload if not FakeGitHub.bad else FakeGitHub.payload[:-1] + b"X"
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()


class Flow(unittest.TestCase):
    def setUp(self):
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (update.API, update.UPDATES_DIR, update.DATA_DIR, update.SETTINGS_FILE)
        update.API = f"http://127.0.0.1:{self.srv.server_address[1]}/release"
        update.DATA_DIR = Path(self.tmp.name)
        update.UPDATES_DIR = Path(self.tmp.name) / "updates"
        update.SETTINGS_FILE = Path(self.tmp.name) / "settings.json"
        update._state.update(phase="idle", latest=None, asset=None, percent=0.0, error=None, path=None, checked=0.0)
        FakeGitHub.bad = False

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        update.API, update.UPDATES_DIR, update.DATA_DIR, update.SETTINGS_FILE = self.saved
        self.tmp.cleanup()

    def wait(self, want):
        for _ in range(100):
            if update.status("1.0.0")["phase"] in want:
                return update.status("1.0.0")
            time.sleep(0.05)
        self.fail("stuck in " + update.status("1.0.0")["phase"])

    def test_check_download_verify(self):
        st = update.check("1.0.0", force=True)
        self.assertEqual((st["phase"], st["latest"]), ("available", "9.9.9"))
        update.start_download()
        st = self.wait(("ready", "available"))
        self.assertEqual(st["phase"], "ready", st.get("error"))
        self.assertEqual(Path(st["path"]).read_bytes(), FakeGitHub.payload)
        self.assertFalse(list(update.UPDATES_DIR.glob("*.part")))

    def test_corrupt_download_is_deleted(self):
        FakeGitHub.bad = True
        update.check("1.0.0", force=True)
        update._state["asset"]["sha256"] = hashlib.sha256(FakeGitHub.payload).hexdigest()     # the checksum of the genuine file
        update.start_download()
        st = self.wait(("ready", "available"))
        self.assertEqual(st["phase"], "available")
        self.assertIn("checksum", st["error"])
        self.assertEqual(list(update.UPDATES_DIR.glob("*")), [])

    def test_up_to_date_and_skip(self):
        self.assertEqual(update.check("9.9.9", force=True)["phase"], "idle")
        update.save_settings({"skipped": "9.9.9"})
        self.assertEqual(update.check("1.0.0", force=True)["phase"], "idle")       # the user skipped this version

    def test_install_refuses_before_ready(self):
        self.assertIn("error", update.install())

    def test_offline_is_quiet(self):
        update.API = "http://127.0.0.1:1/release"
        st = update.check("1.0.0")             # an automatic check says nothing when offline
        self.assertIsNone(st["error"])
        self.assertEqual(st["phase"], "idle")


if __name__ == "__main__":
    unittest.main()
