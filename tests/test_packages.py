"""Missing-package detection: what is found, what is offered, and what the install is allowed to run."""
import time
import unittest
from unittest import mock

from tests import APP  # noqa: F401  (sets sys.path)
import ai
import packages

CODE = "import manimgx as m\nimport numpy as np\nimport math\nimport scipy.integrate\nfrom sklearn import svm\nimport zzz_not_a_real_pkg\n"
SCENE = "\n\nclass S(m.Scene):\n    def construct(self):\n        pass\n"


class Detect(unittest.TestCase):
    def test_the_standard_library_and_the_animation_tools_are_left_out(self):
        mods = [p["module"] for p in packages.scan(CODE)]
        self.assertNotIn("math", mods)
        self.assertNotIn("manimgx", mods)
        self.assertIn("scipy", mods)

    def test_import_names_become_package_names(self):
        self.assertEqual(packages.package_for("cv2"), "opencv-python")
        self.assertEqual(packages.package_for("PIL"), "pillow")
        self.assertEqual(packages.package_for("sklearn"), "scikit-learn")
        self.assertEqual(packages.package_for("my_thing"), "my-thing")

    def test_relative_imports_and_broken_code_give_nothing(self):
        self.assertEqual(packages.imports("from . import x\nfrom .y import z"), [])
        self.assertEqual(packages.imports("def broken(:"), [])

    def test_known_libraries_are_marked(self):
        found = {p["module"]: p for p in packages.scan(CODE)}
        self.assertTrue(found["scipy"]["known"])
        self.assertFalse(found["zzz_not_a_real_pkg"]["known"])
        self.assertEqual(found["scipy"]["line"], 4)


class InTheCheck(unittest.TestCase):
    def test_a_missing_library_is_a_package_issue_not_a_safety_one(self):
        with mock.patch.object(packages, "installed", lambda m: m in ("numpy", "manimgx")):
            issues = ai.quick_check("import manimgx as m\nimport scipy" + SCENE)["issues"]
        pk = [i for i in issues if i["kind"] == "package"]
        self.assertEqual([i["package"] for i in pk], ["scipy"])
        self.assertEqual(pk[0]["line"], 2)
        self.assertFalse([i for i in issues if i["kind"] == "safety"])

    def test_system_access_is_still_blocked(self):
        issues = ai.quick_check("import manimgx as m\nimport os\nimport subprocess" + SCENE)["issues"]
        self.assertEqual(len([i for i in issues if i["kind"] == "safety"]), 2)

    def test_the_assistants_own_code_may_use_only_what_is_installed_and_known(self):
        self.assertTrue(ai.scan_code("import scipy"))                    # not allowed by default
        self.assertFalse(ai.scan_code("import scipy", ["scipy"]))       # allowed once installed
        self.assertTrue(ai.scan_code("import os", ["scipy"]))

    def test_the_layout_check_does_not_run_code_that_cannot_import(self):
        with mock.patch.object(packages, "installed", lambda m: m in ("numpy", "manimgx")), mock.patch.object(ai, "verify_manimgx") as ran:
            res = ai.deep_check("import manimgx as m\nimport scipy" + SCENE)
        self.assertFalse(res["deep"])
        ran.assert_not_called()


class _Lines:
    def __init__(self, lines):
        self.lines = list(lines) + [b""]

    def readline(self):
        return self.lines.pop(0)


class Install(unittest.TestCase):
    def setUp(self):
        packages._job.clear()
        packages._job.update({"state": "idle", "packages": [], "log": [], "step": "", "error": None})

    def test_nothing_missing_nothing_to_do(self):
        with mock.patch.object(packages, "installed", lambda m: True):
            self.assertEqual(packages.start({"code": CODE})[1], 400)

    def test_a_package_not_on_the_list_needs_a_second_confirmation(self):
        with mock.patch.object(packages, "installed", lambda m: False):
            res, status = packages.start({"code": "import zzz_not_a_real_pkg"})
        self.assertEqual(status, 409)
        self.assertEqual(res["needs_confirm"], ["zzz-not-a-real-pkg"])
        self.assertEqual(packages.state()["state"], "idle")

    def test_the_page_cannot_name_a_package_the_code_does_not_import(self):
        with mock.patch.object(packages, "installed", lambda m: False):
            res, status = packages.start({"code": "import scipy", "only": ["evil_pkg"]})
        self.assertEqual(status, 400)

    def test_wheels_only_and_the_name_comes_from_the_code(self):
        seen = {}

        class Proc:
            def __init__(self, cmd, **kw):
                seen["cmd"] = cmd
                self.stdout = _Lines([b"Collecting scipy\n", b"Successfully installed scipy-1.0\n"])

            def wait(self):
                return 0

        with mock.patch.object(packages, "installed", lambda m: False), mock.patch.object(packages.subprocess, "Popen", Proc):
            res, status = packages.start({"code": "import scipy"})
            self.assertEqual(status, 200)
            for _ in range(60):
                if packages.state()["state"] != "running":
                    break
                time.sleep(0.05)
        self.assertEqual(packages.state()["state"], "done")
        self.assertIn("--only-binary", seen["cmd"])
        self.assertEqual(seen["cmd"][seen["cmd"].index("--only-binary") + 1], ":all:")
        self.assertEqual(seen["cmd"][-1], "scipy")

    def test_a_failed_download_says_so_plainly(self):
        class Proc:
            def __init__(self, cmd, **kw):
                self.stdout = _Lines([b"ERROR: No matching distribution found for scipy\n"])

            def wait(self):
                return 1

        with mock.patch.object(packages, "installed", lambda m: False), mock.patch.object(packages.subprocess, "Popen", Proc):
            packages.start({"code": "import scipy"})
            for _ in range(60):
                if packages.state()["state"] != "running":
                    break
                time.sleep(0.05)
        self.assertEqual(packages.state()["state"], "error")
        self.assertIn("ready-made version", packages.state()["error"])


if __name__ == "__main__":
    unittest.main()
