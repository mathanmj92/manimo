"""The code check (ai.quick_check and ai.deep_check) and the assistant's skill modes (ai.skill_prompt)."""
import os
import unittest

from tests import APP  # noqa: F401  (sets sys.path)
import ai

GOOD = "import manimgx as m\n\nclass A(m.Scene):\n    def construct(self):\n        self.play(m.Create(m.Circle()))\n"
VOICEOVER = ("import manimgx as m\n\nclass A(m.Scene):\n    def construct(self):\n        c = m.Circle()\n"
             "        with self.voiceover(text=\"A circle appears.\") as tracker:\n            self.play(m.Create(c))\n")


def kinds(code):
    return [i["kind"] for i in ai.quick_check(code)["issues"]]


class Quick(unittest.TestCase):
    def test_good_code_has_no_issues(self):
        q = ai.quick_check(GOOD)
        self.assertEqual((q["engine"], q["scenes"], q["issues"]), ("manimgx", ["A"], []))

    def test_syntax_error_has_its_line(self):
        q = ai.quick_check(GOOD.replace("m.Circle()))", "m.Circle())"))
        self.assertEqual(q["issues"][0]["kind"], "error")
        self.assertEqual(q["issues"][0]["line"], 5)

    def test_names_that_do_not_exist_get_a_suggestion(self):
        q = ai.quick_check(GOOD.replace("m.Circle", "m.Circl"))
        self.assertIn("m.Circle", q["issues"][0]["text"])
        self.assertEqual(q["issues"][0]["kind"], "name")

    def test_missing_scene_import_construct_and_unsafe_import(self):
        self.assertIn("error", kinds("import manimgx as m\nx = m.Circle()\n"))
        self.assertIn("error", kinds(GOOD.replace("import manimgx as m\n", "")))
        self.assertIn("error", kinds(GOOD.replace("def construct", "def run")))
        self.assertIn("safety", kinds("import os\n" + GOOD))

    def test_manim_ce_code_is_not_name_checked(self):
        q = ai.quick_check("from manim import *\n\nclass A(Scene):\n    def construct(self):\n        self.play(Create(Circle()))\n")
        self.assertEqual((q["engine"], q["issues"]), ("manim", []))

    def test_empty_code(self):
        self.assertEqual(ai.quick_check("  \n")["issues"], [])

    def test_voiceover_scenes_are_not_flagged_statically(self):
        self.assertEqual(ai.quick_check(VOICEOVER)["issues"], [])


class DeepNeedsVoiceSupport(unittest.TestCase):
    def test_inspect_runs_through_run_with_voice(self):
        # a scene that calls self.voiceover must be checked with Manimo's voice support, or it fails with a false error
        import inspect
        self.assertIn("run_with_voice.py", inspect.getsource(ai.verify_manimgx))

    @unittest.skipUnless(os.environ.get("MANIMO_SLOW") == "1", "real inspect run; set MANIMO_SLOW=1")
    def test_voiceover_scene_passes_the_layout_check(self):
        d = ai.deep_check(VOICEOVER, "A")
        self.assertTrue(d["deep"])
        self.assertEqual(d["issues"], [])


class SkillModes(unittest.TestCase):
    def test_plain_request_loads_no_extra_guides(self):
        self.assertEqual(ai.skill_extras("animate the pythagorean theorem")[0], [])

    def test_problem_theory_exam_and_narration_requests(self):
        self.assertIn("problem-solving-pipeline.md", ai.skill_extras("solve this beam problem, find the support reactions")[0])
        self.assertIn("theory-explainer-pipeline.md", ai.skill_extras("explain quantum tunnelling")[0])
        self.assertIn("first-year-exam-mode.md", ai.skill_extras("for first-year exam students")[0])
        self.assertIn("reveal-and-sync.md", ai.skill_extras("make a narrated animation")[0])

    def test_guides_never_mention_files_the_app_does_not_ship(self):
        p = ai.skill_prompt("manimgx", "explain the partition function for a first-year exam, solve a beam problem, narrated")
        self.assertNotIn("_manimo.py", p)
        self.assertNotIn("workspace root", p)

    def test_manim_ce_prompt_stays_small(self):
        self.assertLess(len(ai.skill_prompt("manim", "solve a projectile problem")), 20000)


if __name__ == "__main__":
    unittest.main()
