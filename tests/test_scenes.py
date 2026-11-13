"""Storyboard: scene operations on the text of a file must always give back code that still compiles, and never touch what is not a scene."""
import unittest

from tests import APP  # noqa: F401  (sets sys.path)
import ai
import scenes
import server

CODE = '''import manimgx as m

HELPER = 3


# the opening
class Intro(m.Scene):
    def construct(self):
        t = m.Text("Intro", font_size=40)
        self.say("Hello [there] and welcome.", m.Write(t))
        self.play(m.FadeOut(t))


def helper():
    return 1


class Shapes(m.Scene):
    def construct(self):
        self.play(m.Create(m.Circle()))
        self.wait(0.5)


class Outro(m.Scene):
    def construct(self):
        self.play(m.FadeIn(m.Text("Bye")))
'''


def names(code):
    return [b["name"] for b in scenes.blocks(code)]


class Reading(unittest.TestCase):
    def test_scenes_are_found_with_their_narration_and_animations(self):
        info = scenes.info(CODE)
        self.assertEqual([s["name"] for s in info], ["Intro", "Shapes", "Outro"])
        self.assertEqual((info[0]["words"], info[0]["plays"]), (4, 1))          # the [brackets] around a span are not spoken
        self.assertEqual((info[1]["words"], info[1]["plays"]), (0, 1))
        self.assertGreater(info[0]["est_seconds"], 0)

    def test_a_scene_hash_changes_only_when_that_scene_changes(self):
        before = {s["name"]: s["hash"] for s in scenes.info(CODE)}
        after = {s["name"]: s["hash"] for s in scenes.info(CODE.replace("wait(0.5)", "wait(2)"))}
        self.assertEqual(before["Intro"], after["Intro"])
        self.assertNotEqual(before["Shapes"], after["Shapes"])
        self.assertEqual(before["Outro"], after["Outro"])

    def test_classes_that_are_not_scenes_are_left_alone(self):
        code = CODE + "\n\nclass Helper:\n    pass\n"
        self.assertEqual(names(code), ["Intro", "Shapes", "Outro"])

    def test_broken_code_is_refused_with_a_plain_message(self):
        with self.assertRaises(scenes.SceneError) as cm:
            scenes.info("class A(m.Scene):\n  def construct(self:\n")
        self.assertIn("syntax error", str(cm.exception))


class Editing(unittest.TestCase):
    def test_putting_the_scenes_in_the_same_order_changes_nothing(self):
        self.assertEqual(scenes.reorder(CODE, ["Intro", "Shapes", "Outro"]), CODE)

    def test_reordering_moves_scenes_and_keeps_imports_and_helpers_where_they_are(self):
        new = scenes.reorder(CODE, ["Outro", "Intro", "Shapes"])
        compile(new, "x", "exec")
        self.assertEqual(names(new), ["Outro", "Intro", "Shapes"])
        self.assertTrue(new.startswith("import manimgx as m\n\nHELPER = 3"))
        self.assertIn("def helper():", new)
        self.assertIn("# the opening\nclass Intro", new)                           # a comment above a scene travels with it
        self.assertEqual(new.count("class "), 3)

    def test_reordering_must_list_every_scene_once(self):
        for bad in (["Intro", "Shapes"], ["Intro", "Intro", "Shapes"], ["Intro", "Shapes", "Nope"]):
            with self.assertRaises(scenes.SceneError):
                scenes.reorder(CODE, bad)

    def test_scenes_that_touch_get_two_blank_lines_after_a_reorder(self):
        tight = "import manimgx as m\n\n\nclass A(m.Scene):\n    def construct(self):\n        pass\nclass B(m.Scene):\n    def construct(self):\n        pass\n"
        new = scenes.reorder(tight, ["B", "A"])
        compile(new, "x", "exec")
        self.assertIn("pass\n\n\nclass A", new)

    def test_a_copy_is_named_with_the_next_free_number_and_sits_after_the_original(self):
        new, made = scenes.duplicate(CODE, "Shapes")
        compile(new, "x", "exec")
        self.assertEqual(made, "Shapes_2")
        self.assertEqual(names(new), ["Intro", "Shapes", "Shapes_2", "Outro"])
        again, made2 = scenes.duplicate(new, "Shapes")
        self.assertEqual(made2, "Shapes_3")
        self.assertEqual(len(names(again)), 5)

    def test_deleting_any_scene_leaves_the_rest(self):
        for gone in ("Intro", "Shapes", "Outro"):
            new = scenes.delete(CODE, gone)
            compile(new, "x", "exec")
            self.assertEqual(names(new), [n for n in ("Intro", "Shapes", "Outro") if n != gone])
            self.assertIn("HELPER = 3", new)
            self.assertIn("def helper():", new)

    def test_the_only_scene_cannot_be_deleted(self):
        with self.assertRaises(scenes.SceneError):
            scenes.delete(scenes.delete(scenes.delete(CODE, "Intro"), "Shapes"), "Outro")

    def test_renaming_changes_the_class_and_its_uses_but_not_text_that_happens_to_match(self):
        new = scenes.rename(CODE, "Intro", "Opening")
        compile(new, "x", "exec")
        self.assertEqual(names(new), ["Opening", "Shapes", "Outro"])
        self.assertIn('m.Text("Intro"', new)                                      # a string stays as it was
        sub = CODE + "\n\nclass Extra(Intro):\n    pass\n"
        self.assertIn("class Extra(Opening)", scenes.rename(sub, "Intro", "Opening"))

    def test_bad_names_are_refused(self):
        for bad in ("1abc", "has space", "class", "Shapes", ""):
            with self.assertRaises(scenes.SceneError):
                scenes.rename(CODE, "Intro", bad)


class Templates(unittest.TestCase):
    def test_every_template_compiles_and_uses_only_real_manimgx_names(self):
        for t in scenes.template_list():
            code, name = scenes.add_template("", t["id"])
            compile(code, "x", "exec")
            self.assertEqual(names(code), [name])
            self.assertEqual(ai.check_names(code), [], t["id"])
            self.assertEqual(ai.quick_check(code)["issues"], [], t["id"])

    def test_a_template_is_added_at_the_end_with_a_free_name(self):
        new, name = scenes.add_template(CODE, "title")
        compile(new, "x", "exec")
        self.assertEqual(names(new)[-1], name)
        again, name2 = scenes.add_template(new, "title")
        self.assertNotEqual(name, name2)

    def test_manim_ce_files_get_scenes_without_the_spoken_line(self):
        ce = "from manim import *\n\n\nclass A(Scene):\n    def construct(self):\n        pass\n"
        new, name = scenes.add_template(ce, "summary")
        compile(new, "x", "exec")
        self.assertNotIn("self.say", new)
        self.assertNotIn("m.", new.replace("from manim", ""))


class Plans(unittest.TestCase):
    PLAN = ("Title: A capacitor charging through a resistor\nFor: first-year students; they see why the voltage rises and levels off.\n"
            "Look: blue is voltage, orange is current.\nScenes:\n"
            "1. The circuit - a battery, a switch, R = 10 kOhm and C = 100 uF appear. Narration: Here is a simple RC circuit.\n"
            "2. Charging curve - the voltage graph rises toward 5 V.\n   Narration: The voltage climbs and flattens.\n"
            "Check: viewers confuse time constant with total time; scene 2 marks 1 RC = 1 s.")

    def test_a_plan_becomes_fields_and_scenes(self):
        p = scenes.parse_plan(self.PLAN)
        self.assertEqual(p["title"], "A capacitor charging through a resistor")
        self.assertIn("first-year", p["audience"])
        self.assertEqual([s["name"] for s in p["scenes"]], ["The circuit", "Charging curve"])
        self.assertIn("battery", p["scenes"][0]["sees"])
        self.assertEqual(p["scenes"][1]["narration"], "The voltage climbs and flattens.")
        self.assertIn("time constant", p["check"])

    def test_the_last_scene_does_not_swallow_the_check_line(self):
        p = scenes.parse_plan(self.PLAN)
        self.assertNotIn("Check", p["scenes"][1]["sees"] + p["scenes"][1]["narration"])

    def test_text_that_is_not_a_plan_gives_no_scenes(self):
        self.assertEqual(scenes.parse_plan("Sure, I can help with that.")["scenes"], [])

    def test_class_names_are_safe_and_unique(self):
        self.assertEqual(scenes.class_name("The circuit"), "TheCircuit")
        self.assertEqual(scenes.class_name("3D view"), "Scene3DView")
        self.assertEqual(scenes.class_name("The circuit", ["TheCircuit"]), "TheCircuit2")
        self.assertTrue(scenes.class_name("!!!").isidentifier())


class Api(unittest.TestCase):
    def test_the_route_returns_new_code_and_the_new_scene_list(self):
        res, status = server.scenes_api({"code": CODE, "op": "duplicate", "name": "Outro"})
        self.assertEqual(status, 200)
        self.assertEqual(res["name"], "Outro_2")
        self.assertEqual([s["name"] for s in res["scenes"]][-2:], ["Outro", "Outro_2"])

    def test_problems_come_back_as_plain_400s(self):
        self.assertEqual(server.scenes_api({"code": CODE, "op": "delete", "name": "Nope"})[1], 400)
        self.assertEqual(server.scenes_api({"code": "def f(:", "op": "info"})[1], 400)
        self.assertEqual(server.scenes_api({"code": CODE, "op": "explode"})[1], 400)

    def test_an_empty_editor_has_no_scenes_and_is_not_an_error(self):
        self.assertEqual(server.scenes_api({"code": "", "op": "info"}), ({"scenes": []}, 200))


if __name__ == "__main__":
    unittest.main()
