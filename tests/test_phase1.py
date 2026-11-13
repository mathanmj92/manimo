"""Phase 1: plainer error sentences and the version history."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import APP  # noqa: F401  (sets sys.path)
import history
import server


class FriendlyErrors(unittest.TestCase):
    def test_a_missing_module_names_it_and_points_to_the_check(self):
        msg = server.friendly_error(["Traceback", "ModuleNotFoundError: No module named 'scipy.integrate'"])
        self.assertIn("`scipy`", msg)
        self.assertIn("code check", msg)

    def test_an_unknown_name_gets_the_suggestion_when_python_gave_one(self):
        msg = server.friendly_error(["NameError: name 'Cirle' is not defined. Did you mean: 'Circle'?"])
        self.assertIn("`Cirle`", msg)
        self.assertIn("`Circle`", msg)

    def test_an_unknown_name_without_a_suggestion_still_names_it(self):
        self.assertIn("`foo`", server.friendly_error(["NameError: name 'foo' is not defined"]))

    def test_a_missing_attribute_names_both_sides(self):
        msg = server.friendly_error(["AttributeError: module 'manimgx' has no attribute 'Cirle'. Did you mean: 'Circle'?"])
        self.assertIn("`Cirle`", msg)
        self.assertIn("`Circle`", msg)

    def test_a_syntax_error_says_what_python_said(self):
        self.assertIn("invalid syntax", server.friendly_error(["SyntaxError: invalid syntax"]))
        self.assertIn("unexpected indent", server.friendly_error(["IndentationError: unexpected indent"]))

    def test_latex_and_unknown_failures_keep_their_old_messages(self):
        self.assertIn("LaTeX", server.friendly_error(["latex error converting to dvi"]))
        self.assertIn("engine stopped", server.friendly_error(["something odd"]))


class Versions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = mock.patch.object(history, "DATA_DIR", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_a_snapshot_is_kept_unless_it_is_empty_or_unchanged(self):
        self.assertTrue(history.save({"key": "a.py", "code": "x = 1\n"})[0]["saved"])
        self.assertFalse(history.save({"key": "a.py", "code": "x = 1\n"})[0]["saved"])
        self.assertFalse(history.save({"key": "a.py", "code": "   \n"})[0]["saved"])
        self.assertEqual(len(history.listing({"key": "a.py"})[0]["items"]), 1)

    def test_each_file_has_its_own_history(self):
        history.save({"key": "a.py", "code": "a = 1\n"})
        history.save({"key": "b.py", "code": "b = 1\n"})
        self.assertEqual(len(history.listing({"key": "a.py"})[0]["items"]), 1)
        self.assertEqual(len(history.listing({"key": "B.PY"})[0]["items"]), 1)      # names are not case sensitive on Windows

    def test_the_list_is_newest_first_with_change_counts(self):
        history.save({"key": "a.py", "code": "a = 1\nb = 2\n", "reason": "Edited"})
        history.save({"key": "a.py", "code": "a = 1\nb = 3\nc = 4\n", "reason": "Before render"})
        items = history.listing({"key": "a.py"})[0]["items"]
        self.assertEqual([i["reason"] for i in items], ["Before render", "Edited"])
        self.assertEqual((items[0]["added"], items[0]["removed"]), (2, 1))

    def test_only_the_newest_thirty_are_kept(self):
        for i in range(40):
            history.save({"key": "a.py", "code": f"x = {i}\n"})
        items = history.listing({"key": "a.py"})[0]["items"]
        self.assertEqual(len(items), history.KEEP)
        code = history.get({"key": "a.py", "id": items[0]["id"], "code": ""})[0]["code"]
        self.assertEqual(code, "x = 39\n")

    def test_a_version_comes_back_with_its_difference_from_the_editor(self):
        history.save({"key": "a.py", "code": "a = 1\nb = 2\n"})
        sid = history.listing({"key": "a.py"})[0]["items"][0]["id"]
        res, status = history.get({"key": "a.py", "id": sid, "code": "a = 1\nb = 9\n"})
        self.assertEqual(status, 200)
        self.assertFalse(res["same"])
        self.assertIn("-b = 2", res["diff"])
        self.assertIn("+b = 9", res["diff"])
        self.assertTrue(history.get({"key": "a.py", "id": sid, "code": "a = 1\nb = 2\n"})[0]["same"])

    def test_an_unknown_version_is_a_plain_404_and_a_broken_file_is_not_a_crash(self):
        self.assertEqual(history.get({"key": "a.py", "id": "nope"})[1], 404)
        history.save({"key": "a.py", "code": "a = 1\n"})
        for f in Path(self.tmp.name).glob("*.json"):
            f.write_text("{broken", encoding="utf-8")
        self.assertEqual(history.listing({"key": "a.py"})[0]["items"], [])


if __name__ == "__main__":
    unittest.main()
