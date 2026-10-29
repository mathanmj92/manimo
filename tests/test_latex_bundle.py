import os
import tempfile
import unittest
from pathlib import Path

from tests import APP  # noqa: F401  (sets sys.path)
import server


class BundledTexlive(unittest.TestCase):
    def _app(self, with_tex):
        root = Path(tempfile.mkdtemp(prefix="manimo-test-"))
        (root / "python").mkdir()
        (root / "python" / "python.exe").write_bytes(b"")
        if with_tex:
            bindir = root / "texlive" / "bin" / "windows"
            bindir.mkdir(parents=True)
            (bindir / "latex.exe").write_bytes(b"")
            (bindir / "dvisvgm.exe").write_bytes(b"")
        return root

    def test_found_next_to_the_private_python(self):
        root = self._app(True)
        self.assertEqual(server.bundled_texlive_bin(root / "python" / "python.exe"), (root / "texlive" / "bin" / "windows").resolve())

    def test_none_when_the_component_is_not_installed(self):
        root = self._app(False)
        self.assertIsNone(server.bundled_texlive_bin(root / "python" / "python.exe"))

    def test_none_when_dvisvgm_is_missing(self):
        root = self._app(True)
        (root / "texlive" / "bin" / "windows" / "dvisvgm.exe").unlink()
        self.assertIsNone(server.bundled_texlive_bin(root / "python" / "python.exe"))


class TexEnv(unittest.TestCase):
    def test_bundled_latex_goes_first_and_the_input_is_untouched(self):
        env = {"PATH": r"C:\Windows", "TEXMFHOME": r"C:\elsewhere", "TEXINPUTS": "x", "KEEP": "1"}
        out = server.tex_env(env, Path(r"C:\Manimo\texlive\bin\windows"))
        self.assertTrue(out["PATH"].startswith(r"C:\Manimo\texlive\bin\windows" + os.pathsep))
        self.assertTrue(out["PATH"].endswith(r"C:\Windows"))
        self.assertNotIn("TEXMFHOME", out)
        self.assertNotIn("TEXINPUTS", out)
        self.assertEqual(out["KEEP"], "1")
        self.assertEqual(env["PATH"], r"C:\Windows")
        self.assertIn("TEXMFHOME", env)

    def test_without_a_bundle_the_environment_is_unchanged(self):
        env = {"PATH": "a", "TEXMFHOME": "b"}
        self.assertEqual(server.tex_env(env, None), env)


class LatexVersion(unittest.TestCase):
    def test_first_line_of_pdftex(self):
        text = "pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)\nkpathsea version 6.4.1\nCopyright 2026 Han The Thanh\n"
        self.assertEqual(server.parse_latex_version(text), "pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)")

    def test_miktex_line(self):
        self.assertIn("MiKTeX", server.parse_latex_version("MiKTeX-pdfTeX 4.20 (MiKTeX 24.1)\nmore"))

    def test_nothing_useful(self):
        self.assertIsNone(server.parse_latex_version(""))
        self.assertIsNone(server.parse_latex_version(None))
        self.assertIsNone(server.parse_latex_version("not recognised"))


if __name__ == "__main__":
    unittest.main()
