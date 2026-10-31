"""Add-on pack (Manim CE + LaTeX downloaded after install): checksum rules, safe unpacking, and the release lookup and
download against a small local server that pretends to be GitHub. The real GitHub is never contacted."""
import hashlib
import http.server
import io
import json
import tempfile
import threading
import unittest
import zipfile
from unittest import mock
from pathlib import Path

from tests import APP  # noqa: F401  (sets sys.path)
import addon


class Helpers(unittest.TestCase):
    def test_names(self):
        self.assertEqual(addon.pack_name("v1.9.6"), "Manimo-CE-LaTeX-Pack-1.9.6.zip")
        self.assertEqual(addon.find_pack([{"name": "x"}, {"name": "Manimo-CE-LaTeX-Pack-1.9.6.zip"}], "1.9.6")["name"], "Manimo-CE-LaTeX-Pack-1.9.6.zip")
        self.assertIsNone(addon.find_pack([{"name": "Manimo-CE-LaTeX-Pack-1.9.5.zip"}], "1.9.6"))

    def test_checksums(self):
        h = "b" * 64
        sums = f"{'a' * 64}  other.zip\n{h.upper()} *Manimo-CE-LaTeX-Pack-1.9.6.zip\n"
        self.assertEqual(addon.sha_from_sums(sums, "Manimo-CE-LaTeX-Pack-1.9.6.zip"), h)
        self.assertIsNone(addon.sha_from_sums(sums, "missing.zip"))
        assets = [{"name": "Manimo-CE-LaTeX-Pack-1.9.6.zip", "digest": "sha256:" + h}]
        self.assertEqual(addon.pack_sha256(assets, "1.9.6"), h)                      # GitHub's digest wins
        self.assertEqual(addon.pack_sha256([{"name": "Manimo-CE-LaTeX-Pack-1.9.6.zip"}], "1.9.6", sums), h)
        self.assertIsNone(addon.pack_sha256([{"name": "Manimo-CE-LaTeX-Pack-1.9.6.zip"}], "1.9.6", ""))

    def test_safe_members(self):
        self.assertEqual(addon.safe_members(["texlive/bin/windows/latex.exe", "wheels-ce/a.whl"]), ["texlive/bin/windows/latex.exe", "wheels-ce/a.whl"])
        for bad in ("../evil.txt", "/etc/passwd", "C:/Windows/x.dll", "a/../../b", "..\\evil"):
            with self.assertRaises(addon.AddonError, msg=bad):
                addon.safe_members([bad])

    def test_incomplete_pack_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            z = Path(d) / "p.zip"
            with zipfile.ZipFile(z, "w") as f:
                f.writestr("wheels-ce/readme.txt", "x")        # no requirements file, no TeX tree
            with self.assertRaises(addon.AddonError):
                addon.install_pack(z, Path(d), lambda *a: None)
            self.assertFalse((Path(d) / "texlive").exists())

    def test_install_root_needs_the_private_python(self):
        with tempfile.TemporaryDirectory() as d:
            other = Path(d) / "bin" / "python.exe"          # some other Python, not <root>\\python\\python.exe next to an app folder
            other.parent.mkdir()
            with mock.patch.object(addon.sys, "executable", str(other)):
                self.assertIsNone(addon.install_root())
            root = Path(d) / "Manimo"
            (root / "python").mkdir(parents=True)
            (root / "app").mkdir()
            priv = root / "python" / "python.exe"
            priv.write_bytes(b"")
            with mock.patch.object(addon.sys, "executable", str(priv)):
                self.assertEqual(addon.install_root(), root.resolve())


class FakeGitHub(http.server.BaseHTTPRequestHandler):
    payload = b"PK-not-really-a-zip" * 5000
    sums_ok = True

    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        port = self.server.server_address[1]
        if self.path == "/repos/releases/tags/v9.9.9":
            self._send(json.dumps({"tag_name": "v9.9.9", "assets": [
                {"name": "Manimo-CE-LaTeX-Pack-9.9.9.zip", "size": len(self.payload), "browser_download_url": f"http://127.0.0.1:{port}/pack"},
                {"name": "SHA256SUMS.txt", "browser_download_url": f"http://127.0.0.1:{port}/sums"}]}).encode())
        elif self.path == "/repos/releases/tags/v8.8.8":
            self._send(json.dumps({"tag_name": "v8.8.8", "assets": []}).encode())
        elif self.path == "/sums":
            h = hashlib.sha256(self.payload).hexdigest() if FakeGitHub.sums_ok else "0" * 64
            self._send((h + "  Manimo-CE-LaTeX-Pack-9.9.9.zip\n").encode(), "text/plain")
        elif self.path == "/pack":
            self._send(self.payload, "application/octet-stream")
        else:
            self.send_response(404)
            self.end_headers()


class Network(unittest.TestCase):
    def setUp(self):
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.api = f"http://127.0.0.1:{self.srv.server_address[1]}/repos"
        FakeGitHub.sums_ok = True

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_lookup_and_download(self):
        asset, sha = addon.release_info("9.9.9", self.api)
        self.assertEqual(sha, hashlib.sha256(FakeGitHub.payload).hexdigest())
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / asset["name"]
            seen = []
            addon.download(asset, sha, dest, lambda step, pct: seen.append(pct), lambda: False)
            self.assertEqual(dest.read_bytes(), FakeGitHub.payload)
            self.assertTrue(seen and seen[-1] == 100.0)
            self.assertFalse(list(Path(d).glob("*.part")))

    def test_wrong_checksum_is_deleted(self):
        asset, sha = addon.release_info("9.9.9", self.api)
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / asset["name"]
            with self.assertRaises(addon.AddonError) as cm:
                addon.download(asset, "0" * 64, dest, lambda *a: None, lambda: False)
            self.assertIn("checksum", str(cm.exception))
            self.assertEqual(list(Path(d).glob("*")), [])

    def test_cancel(self):
        asset, sha = addon.release_info("9.9.9", self.api)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(addon.AddonError):
                addon.download(asset, sha, Path(d) / "x.zip", lambda *a: None, lambda: True)
            self.assertEqual(list(Path(d).glob("*")), [])

    def test_no_pack_published(self):
        with self.assertRaises(addon.NoPack):
            addon.release_info("8.8.8", self.api)        # a release without the add-on
        with self.assertRaises(addon.NoPack):
            addon.release_info("7.7.7", self.api)        # no such release (404)

    def test_run_needs_the_installed_app(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(addon.sys, "executable", str(Path(d) / "python.exe")):
            with self.assertRaises(addon.AddonError):          # never installs anything unless it is the private Python
                addon.run("9.9.9", lambda *a: None, lambda: False, d, self.api)


if __name__ == "__main__":
    unittest.main()
