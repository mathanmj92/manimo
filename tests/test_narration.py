"""Phase 3: spoken lines, voice and speed per scene, pronunciations and the assistant's rewrite. None of it may change anything but the words."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import APP  # noqa: F401  (sets sys.path)
import ai
import narration
import project
import scenes
import server
import voice

CODE = '''import manimgx as m


# the opening
class Intro(m.Scene):
    def construct(self):
        t = m.Text("Hi")
        self.say("Hello [there] and welcome to \\"class\\".", m.Write(t))
        self.say(
            "A long line "
            "split over two lines.",
            m.FadeOut(t),
        )


class Shapes(m.Scene):
    def construct(self):
        with self.voiceover(text="Old style narration.") as tr:
            self.play(m.Create(m.Circle()))
        self.say("é ü and sin theta", m.Create(m.Square()))
'''


class Lines(unittest.TestCase):
    def test_every_spoken_line_is_found_in_order_with_its_text(self):
        got = [(l["scene"], l["n"], l["text"], l["kind"]) for l in narration.public(CODE)]
        self.assertEqual(got, [("Intro", 0, 'Hello [there] and welcome to "class".', "say"), ("Intro", 1, "A long line split over two lines.", "say"),
                               ("Shapes", 0, "Old style narration.", "voiceover"), ("Shapes", 1, "é ü and sin theta", "say")])

    def test_only_the_words_change_and_the_rest_of_the_file_is_untouched(self):
        new = narration.set_lines(CODE, [{"scene": "Intro", "n": 0, "text": 'Hello [again] and "quoted" \\ back'}, {"scene": "Shapes", "n": 1, "text": "é ü and sine theta"}])
        compile(new, "x", "exec")
        got = {(l["scene"], l["n"]): l["text"] for l in narration.public(new)}
        self.assertEqual(got[("Intro", 0)], 'Hello [again] and "quoted" \\ back')       # quotes and backslashes survive the round trip
        self.assertEqual(got[("Shapes", 1)], "é ü and sine theta")             # accented letters land in the right place
        self.assertEqual(got[("Intro", 1)], "A long line split over two lines.")
        stripped = lambda c: [ln for ln in c.split("\n") if "say(" not in ln]
        self.assertEqual(stripped(new)[:6], stripped(CODE)[:6])

    def test_a_line_keeps_one_bracketed_part_for_each_animation(self):
        for bad in ("no brackets now", "two [brackets] [here]"):
            with self.assertRaises(narration.NarrationError):
                narration.set_lines(CODE, [{"scene": "Intro", "n": 0, "text": bad}])

    def test_empty_unknown_and_stale_edits_are_refused(self):
        for bad in ({"scene": "Intro", "n": 0, "text": "   "}, {"scene": "Nope", "n": 0, "text": "x"}, {"scene": "Intro", "n": 9, "text": "x"}):
            with self.assertRaises(narration.NarrationError):
                narration.set_lines(CODE, [bad])

    def test_an_unchanged_line_makes_no_change_at_all(self):
        self.assertEqual(narration.set_lines(CODE, [{"scene": "Intro", "n": 1, "text": "A long line split over two lines."}]), CODE)


class SceneSettings(unittest.TestCase):
    def test_voice_and_speed_go_in_the_comments_above_the_scene_and_come_out_again(self):
        new = narration.set_scene_settings(CODE, "Intro", "bf_emma", 1.1)
        self.assertIn("# the opening\n# voice: bf_emma\n# speed: 1.1\nclass Intro", new)
        self.assertEqual(narration.scene_settings(new)["Intro"], {"voice": "bf_emma", "speed": 1.1})
        self.assertEqual(narration.scene_settings(new)["Shapes"], {"voice": None, "speed": None})
        self.assertEqual(narration.set_scene_settings(new, "Intro", None, None), CODE)

    def test_the_settings_travel_with_the_scene_when_scenes_are_reordered(self):
        new = scenes.reorder(narration.set_scene_settings(CODE, "Intro", "bf_emma", None), ["Shapes", "Intro"])
        self.assertEqual(narration.scene_settings(new)["Intro"]["voice"], "bf_emma")

    def test_bad_voices_and_speeds_are_refused(self):
        with self.assertRaises(narration.NarrationError):
            narration.set_scene_settings(CODE, "Intro", "not_a_voice", None)
        with self.assertRaises(narration.NarrationError):
            narration.set_scene_settings(CODE, "Intro", None, "fast")
        with self.assertRaises(narration.NarrationError):
            narration.set_scene_settings(CODE, "Nope", "bf_emma", None)

    def test_speed_is_kept_within_what_the_voice_handles(self):
        self.assertEqual(narration.scene_settings(narration.set_scene_settings(CODE, "Intro", None, 5))["Intro"]["speed"], 1.4)


class Pronunciation(unittest.TestCase):
    def tearDown(self):
        voice.set_pronunciations([], True)

    def test_written_words_are_spoken_differently_but_only_when_spoken(self):
        voice.set_pronunciations([("mu_k", "mu k")])
        self.assertEqual(voice.pronounce("The coefficient mu_k is small"), "The coefficient mu k is small")

    def test_whole_words_only_and_symbols_anywhere(self):
        voice.set_pronunciations([("sin", "sine")], defaults=False)
        self.assertEqual(voice.pronounce("sin of the sinking ship"), "sine of the sinking ship")
        voice.set_pronunciations([], defaults=True)
        self.assertEqual(voice.pronounce("x² and 2π and 10 kΩ"), "x squared and 2 pi and 10 kilo ohms")

    def test_the_file_lists_them_and_can_turn_the_built_in_list_off(self):
        new = narration.set_pronunciations(CODE, [("mu_k", "mu k"), ("theta", "thay ta")], defaults=False)
        self.assertTrue(new.startswith("# say-defaults: off\n# say: mu_k = mu k\n# say: theta = thay ta\n\nimport manimgx"))
        got = narration.pronunciations(new)
        self.assertEqual((got["pairs"], got["defaults"]), ([["mu_k", "mu k"], ["theta", "thay ta"]], False))
        self.assertEqual(narration.set_pronunciations(new, [], True), CODE)           # taking them all out gives the file back exactly
        again = narration.set_pronunciations(new, [("a", "b")], True)
        self.assertEqual(again.count("# say"), 1)                                      # saving twice does not pile up lines or blank lines
        self.assertTrue(again.startswith("# say: a = b\n\nimport"))

    def test_half_filled_rows_are_refused_and_empty_rows_ignored(self):
        with self.assertRaises(narration.NarrationError):
            narration.set_pronunciations(CODE, [("theta", "")])
        with self.assertRaises(narration.NarrationError):
            narration.set_pronunciations(CODE, [("a=b", "c")])
        self.assertEqual(narration.set_pronunciations(CODE, [("", "")], True), CODE)

    def test_a_scene_gets_the_files_pronunciations_and_its_own_voice_when_rendered(self):
        code = "# say: theta = thay ta\n" + narration.set_scene_settings(CODE, "Intro", "bf_emma", 1.2)
        self.assertEqual(voice.configure(code, "Intro", "am_adam", 1.0), ("bf_emma", 1.2))
        self.assertEqual(voice.configure(code, "Shapes", "am_adam", 1.0), ("am_adam", 1.0))
        self.assertEqual(voice.pronounce("theta"), "thay ta")

    def test_the_render_finds_the_file_and_scene_in_the_command_line(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "scene.py"
            f.write_text("x = 1\n", encoding="utf-8")
            self.assertEqual(voice.source_and_scene(["render", str(f), "Intro", "-o", "x.mp4"]), (str(f), "Intro"))
            self.assertEqual(voice.source_and_scene(["inspect", str(f), "-o", "x.png"]), (str(f), None))
            self.assertEqual(voice.source_and_scene(["--version"]), (None, None))


class Api(unittest.TestCase):
    def test_the_route_returns_new_code_and_refreshed_lines(self):
        res, status = server.narration_api({"code": CODE, "op": "set", "edits": [{"scene": "Intro", "n": 1, "text": "Shorter."}]})
        self.assertEqual(status, 200)
        self.assertEqual([l["text"] for l in res["lines"] if l["scene"] == "Intro"][1], "Shorter.")
        self.assertIn("Shorter.", res["code"])

    def test_problems_come_back_as_plain_400s(self):
        self.assertEqual(server.narration_api({"code": CODE, "op": "set", "edits": [{"scene": "Intro", "n": 0, "text": "none"}]})[1], 400)
        self.assertEqual(server.narration_api({"code": "def f(:", "op": "lines"})[1], 400)
        self.assertEqual(server.narration_api({"code": CODE, "op": "boom"})[1], 400)


class Rewrite(unittest.TestCase):
    def run_rewrite(self, answer, style="shorter", scene=""):
        seen = {}

        def fake(cfg, system, messages, on_delta, max_tokens=0):
            seen.update(system=system, user=messages[-1]["content"])
            on_delta(answer)
        with mock.patch.object(ai, "stream", fake), mock.patch.object(ai, "load_settings", lambda: {"provider": "agent", "agent": "claude"}):
            ai._job.clear()
            res, status = ai.rewrite_narration({"code": CODE, "style": style, "scene": scene, "level": "students in class 9"})
        return res, status, seen

    def test_only_the_spoken_words_are_sent_not_the_code(self):
        _, _, seen = self.run_rewrite(json.dumps({"1": 'Hello [there] and welcome to "class".'}))
        self.assertIn("1. Hello [there]", seen["user"])
        self.assertNotIn("construct", seen["user"])
        self.assertNotIn("m.Write", seen["user"])
        self.assertIn("class 9", seen["user"])
        self.assertEqual(seen["system"], ai.REWRITE_SYSTEM)

    def test_a_good_rewrite_is_applied_and_one_that_loses_its_brackets_keeps_the_old_words(self):
        res, status, _ = self.run_rewrite("Sure: " + json.dumps({"1": "Hello [there].", "2": "Short, but the brackets are gone"}).replace("Short,", "Short"), scene="")
        self.assertEqual(status, 200)
        texts = {(l["scene"], l["n"]): l["text"] for l in res["lines"]}
        self.assertEqual(texts[("Intro", 0)], "Hello [there].")
        self.assertEqual(res["changed"], 2)            # lines 1 and 2 (line 2 has no brackets in the original, so it may change)

    def test_a_rewrite_that_drops_a_bracket_is_skipped_per_line(self):
        res, _, _ = self.run_rewrite(json.dumps({"1": "Hello there with no brackets."}))
        self.assertEqual(res["changed"], 0)
        self.assertEqual(len(res["skipped"]), 1)
        self.assertEqual(res["code"], CODE)

    def test_unreadable_answers_and_bad_styles_are_plain_errors(self):
        self.assertEqual(self.run_rewrite("I could not do that")[1], 502)
        self.assertEqual(self.run_rewrite("{}", style="louder")[1], 400)
        self.assertEqual(ai.rewrite_narration({"code": "x = 1\n", "style": "shorter"})[1], 400)


class Subtitles(unittest.TestCase):
    def test_the_default_look_is_what_exports_had_before(self):
        self.assertEqual(project.caption_style(None, 1280, 720), "FontName=Segoe UI,FontSize=14,Shadow=0,MarginV=20,Alignment=2,PrimaryColour=&H00FFFFFF,Outline=2")

    def test_tall_videos_get_smaller_type_and_size_scales_it(self):
        self.assertIn("FontSize=8,", project.caption_style({}, 720, 1280))
        self.assertIn("FontSize=19,", project.caption_style({"size": "large"}, 1280, 720))
        self.assertIn("FontSize=11,", project.caption_style({"size": "small"}, 1280, 720))

    def test_position_colour_and_box_are_applied(self):
        s = project.caption_style({"position": "top", "color": "yellow", "box": True}, 1280, 720)
        for part in ("Alignment=6", "PrimaryColour=&H0000FFFF", "BorderStyle=3", "BackColour=&H99000000"):
            self.assertIn(part, s)
        self.assertIn("Alignment=10", project.caption_style({"position": "middle"}, 1280, 720))

    def test_nothing_from_the_page_can_reach_the_filter_text(self):
        s = project.caption_style({"size": "x'; drm", "position": "../..", "color": "red;[x]", "box": "yes"}, 1280, 720)
        self.assertNotIn("'", s)
        self.assertNotIn(";", s)
        self.assertNotIn("[", s)
        self.assertIn("Alignment=2", s)
        self.assertIn("PrimaryColour=&H00FFFFFF", s)

    def test_the_preview_is_a_real_picture_in_the_shape_asked_for(self):
        ff = server.ffmpeg_exe()
        if not ff:
            self.skipTest("ffmpeg is not available")
        with mock.patch.dict(project._deps, {"ffmpeg_exe": lambda: ff}):
            wide = project.caption_preview({"position": "middle", "box": True})
            tall = project.caption_preview({}, "9:16")
        self.assertEqual((wide["width"], wide["height"]), (640, 360))
        self.assertEqual((tall["width"], tall["height"]), (360, 640))
        self.assertTrue(wide["image"].startswith("data:image/jpeg;base64,"))
        self.assertGreater(len(wide["image"]), 1500)


if __name__ == "__main__":
    unittest.main()
