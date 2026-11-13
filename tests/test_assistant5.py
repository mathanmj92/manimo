"""Phase 5: what a request costs, taking a scene from one of the assistant's takes, scene previews, and saved conversations."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import APP  # noqa: F401  (sets sys.path)
import ai
import chats
import scenes
import server

BASE = '''import manimgx as m


class Intro(m.Scene):
    def construct(self):
        self.play(m.FadeIn(m.Text("Hello")))


class Solve(m.Scene):
    def construct(self):
        self.play(m.Create(m.Circle()))
'''
TAKE = '''import manimgx as m
import numpy as np
from manimgx import config


class Intro(m.Scene):
    def construct(self):
        self.play(m.FadeIn(m.Text("CHANGED")))


class Solve(m.Scene):
    def construct(self):
        pts = [np.array([x, x * x / 4, 0]) for x in range(-2, 3)]
        self.play(m.Create(m.Polygon(*pts)))
'''


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        for p in (mock.patch.object(ai, "USAGE_FILE", d / "usage.json"), mock.patch.object(chats, "FILE", d / "chats.json")):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        ai.begin_usage()


class Usage(Sandbox):
    def test_the_providers_own_counts_are_used_when_it_gives_them(self):
        ai._tally("sys", [{"role": "user", "content": "hi"}], "reply", {"in": 9000, "out": 1200}, 4.0)
        s = ai.usage_snapshot()
        self.assertEqual((s["in"], s["out"], s["calls"], s["exact"]), (9000, 1200, 1, True))

    def test_without_counts_it_is_about_four_characters_a_token_and_says_so(self):
        ai._tally("s" * 400, [{"role": "user", "content": "u" * 400}], "r" * 80, {}, 1.0)
        s = ai.usage_snapshot()
        self.assertEqual((s["in"], s["out"], s["exact"]), (200, 20, False))

    def test_one_estimated_call_makes_the_whole_request_an_estimate(self):
        ai._tally("a", [], "b", {"in": 10, "out": 5}, 1)
        ai._tally("a", [], "b", {}, 1)
        self.assertFalse(ai.usage_snapshot()["exact"])
        ai.begin_usage()
        self.assertEqual(ai.usage_snapshot()["calls"], 0)

    def test_the_month_adds_up_on_this_pc_and_a_new_request_is_counted_once(self):
        ai._tally("a", [], "b", {"in": 100, "out": 50}, 3.0)
        ai._tally("a", [], "b", {"in": 200, "out": 70}, 2.5)
        ai.count_request()
        m = ai.usage_summary()
        self.assertEqual((m["in"], m["out"], m["requests"], m["seconds"]), (300, 120, 1, 5.5))
        self.assertEqual(m["month"][:2], "20")

    def test_a_damaged_usage_file_starts_again_instead_of_failing(self):
        ai.USAGE_FILE.write_text("{nope", encoding="utf-8")
        self.assertEqual(ai.usage_summary()["requests"], 0)
        ai.count_request()
        self.assertEqual(ai.usage_summary()["requests"], 1)

    def test_the_stream_wrapper_tallies_every_call_even_when_it_fails(self):
        def fake(cfg, system, messages, on_delta, max_tokens=0):
            ai._tl.exact.update({"in": 500, "out": 40})
            on_delta("hello")
            raise ai.AIError("boom")
        with mock.patch.object(ai, "_stream_once", fake), self.assertRaises(ai.AIError):
            ai.stream({"provider": "anthropic"}, "s", [{"role": "user", "content": "x"}], lambda p: None, 10)
        self.assertEqual(ai.usage_snapshot()["in"], 500)

    def test_a_finished_request_reports_what_it_cost(self):
        def fake_stream(cfg, system, messages, on_delta, max_tokens=0):
            ai._tally(system, messages, "Given: x\nAnswer: 3", {"in": 7000, "out": 300}, 2.0)
            on_delta("Given: x\nAnswer: 3")
        with mock.patch.object(ai, "stream", fake_stream), mock.patch.object(ai, "load_settings", lambda: {"provider": "agent", "agent": "claude"}):
            ai._job.clear()
            ai._job.update({"state": "running", "steps": [], "text": "", "final": None, "error": None})
            ai.run({"prompt": "Solve this problem: a 10 kg block slides down a rough incline of 30 degrees, mu = 0.25. Find a.", "mode": "write", "solve_first": True, "history": []})
        u = ai._job["final"]["usage"]
        self.assertEqual((u["in"], u["out"], u["calls"], u["exact"]), (7000, 300, 1, True))
        self.assertGreaterEqual(u["seconds"], 0)
        self.assertEqual(ai.usage_summary()["requests"], 1)

    def test_the_route_returns_the_month(self):
        self.assertEqual(ai.handle("GET", "/api/ai/usage", {})[0]["requests"], 0)


class TakeReplacement(unittest.TestCase):
    def test_only_the_chosen_scene_is_taken_and_the_new_import_comes_with_it(self):
        new = scenes.replace(BASE, "Solve", TAKE)
        compile(new, "x", "exec")
        self.assertIn("m.Polygon", new)
        self.assertIn("m.Text(\"Hello\")", new)                     # the other scene is as it was
        self.assertNotIn("CHANGED", new)
        self.assertIn("import numpy as np", new)
        self.assertIn("from manimgx import config", new)
        self.assertTrue(new.startswith("import manimgx as m\nimport numpy as np\nfrom manimgx import config\n"))

    def test_nothing_is_added_that_is_already_imported(self):
        again = scenes.replace(scenes.replace(BASE, "Solve", TAKE), "Solve", TAKE)
        self.assertEqual(again.count("import numpy as np"), 1)

    def test_a_take_without_the_scene_or_with_broken_code_is_refused(self):
        with self.assertRaises(scenes.SceneError):
            scenes.replace(BASE, "Solve", "import manimgx as m\n\n\nclass Other(m.Scene):\n    def construct(self):\n        pass\n")
        with self.assertRaises(scenes.SceneError):
            scenes.replace(BASE, "Nope", TAKE)
        with self.assertRaises(scenes.SceneError):
            scenes.replace(BASE, "Solve", "def broken(:")

    def test_the_route_does_the_same(self):
        res, status = server.scenes_api({"code": BASE, "op": "replace", "name": "Solve", "take": TAKE})
        self.assertEqual(status, 200)
        self.assertIn("Polygon", res["code"])
        self.assertEqual(server.scenes_api({"code": BASE, "op": "replace", "name": "Solve", "take": ""})[1], 400)

    def test_a_scene_card_knows_where_its_block_starts_for_the_assistant(self):
        info = scenes.info("import manimgx as m\n\n\n# the intro\nclass A(m.Scene):\n    def construct(self):\n        pass\n")
        self.assertEqual((info[0]["start"], info[0]["line"], info[0]["end"]), (4, 5, 7))


class ScenePreview(unittest.TestCase):
    def test_a_real_scene_gives_a_picture_and_what_the_check_found(self):
        res, status = server.scene_preview({"code": TAKE, "scene": "Solve"})
        self.assertEqual(status, 200)
        self.assertTrue(res["image"].startswith("data:image/"))
        self.assertIsNone(res["error"])
        self.assertEqual(res["plays"], 1)

    def test_code_that_cannot_run_says_why_without_running_it(self):
        res, status = server.scene_preview({"code": BASE.replace("m.Circle()", "m.Cirle()"), "scene": "Solve"})
        self.assertEqual(status, 200)
        self.assertIsNone(res["image"])
        self.assertIn("Cirle", res["error"])

    def test_unknown_scenes_and_other_engines_are_plain_errors(self):
        self.assertEqual(server.scene_preview({"code": BASE, "scene": "Nope"})[1], 400)
        self.assertEqual(server.scene_preview({"code": "from manim import *\n\n\nclass A(Scene):\n    def construct(self):\n        pass\n", "scene": "A"})[1], 400)


class Conversations(Sandbox):
    def convo(self, text="Teach me how a capacitor charges", **kw):
        return {"key": "Physics.py", "msgs": [{"role": "user", "text": text}, {"role": "assistant", "text": "Here is a plan.", "code": "x = 1", "kind": "plan", "steps": [{"big": "x" * 5000}], "usage": {"in": 10, "out": 5, "exact": True, "bogus": 1}}], **kw}

    def test_a_conversation_is_saved_titled_by_what_was_asked_and_found_again(self):
        cid = chats.save(self.convo())[0]["id"]
        items = chats.listing({"key": "Physics.py"})[0]["items"]
        self.assertEqual([i["id"] for i in items], [cid])
        self.assertEqual(items[0]["title"], "Teach me how a capacitor charges")
        got = chats.get({"id": cid})[0]
        self.assertEqual(got["msgs"][1]["kind"], "plan")
        self.assertNotIn("steps", got["msgs"][1])                                     # bulky step logs are not kept
        self.assertEqual(got["msgs"][1]["usage"], {"in": 10, "out": 5, "exact": True})

    def test_saving_again_updates_the_same_conversation(self):
        cid = chats.save(self.convo())[0]["id"]
        again = self.convo(id=cid)
        again["msgs"].append({"role": "user", "text": "Make it shorter"})
        self.assertEqual(chats.save(again)[0]["id"], cid)
        self.assertEqual(len(chats.listing({})[0]["items"]), 1)
        self.assertEqual(chats.listing({})[0]["items"][0]["n"], 3)

    def test_a_chat_with_no_question_is_not_kept(self):
        self.assertIsNone(chats.save({"key": "a", "msgs": []})[0]["id"])
        self.assertEqual(chats.listing({})[0]["items"], [])

    def test_search_looks_in_titles_and_in_every_message_and_shows_where(self):
        chats.save(self.convo())
        other = {"key": "Maths.py", "msgs": [{"role": "user", "text": "Explain the derivative"}, {"role": "assistant", "text": "The slope of a tangent line at a point."}]}
        chats.save(other)
        self.assertEqual([i["key"] for i in chats.listing({"q": "capacitor"})[0]["items"]], ["Physics.py"])
        hit = chats.listing({"q": "tangent"})[0]["items"]
        self.assertEqual(len(hit), 1)
        self.assertIn("tangent", hit[0]["snippet"])
        self.assertEqual(chats.listing({"q": "tangent", "key": "Physics.py"})[0]["items"], [])

    def test_pinned_conversations_come_first_and_survive_trimming(self):
        pinned = chats.save(self.convo("Keep this one"))[0]["id"]
        chats.pin({"id": pinned, "pinned": True})
        with mock.patch.object(chats, "KEEP_PER_LESSON", 2):
            for i in range(5):
                chats.save(self.convo(f"Question {i}"))
        items = chats.listing({"key": "Physics.py"})[0]["items"]
        self.assertEqual(items[0]["id"], pinned)
        self.assertTrue(items[0]["pinned"])
        self.assertEqual(len(items), 3)                                                # the pinned one and the newest two

    def test_the_file_stays_under_its_size_limit(self):
        with mock.patch.object(chats, "MAX_BYTES", 6000):
            for i in range(12):
                chats.save({"key": f"L{i}.py", "msgs": [{"role": "user", "text": "q" * 1000}]})
        self.assertLess(len(chats.FILE.read_text(encoding="utf-8")), 7500)

    def test_delete_and_unknown_ids_and_a_damaged_file(self):
        cid = chats.save(self.convo())[0]["id"]
        chats.delete({"id": cid})
        self.assertEqual(chats.get({"id": cid})[1], 404)
        self.assertEqual(chats.pin({"id": "nope", "pinned": True})[1], 404)
        chats.FILE.write_text("{nope", encoding="utf-8")
        self.assertEqual(chats.listing({})[0]["items"], [])

    def test_big_code_and_long_chats_are_cut_down(self):
        msgs = []
        for i in range(45):
            msgs += [{"role": "user", "text": f"question {i}"}, {"role": "assistant", "text": "t", "code": "x" * 200_000}]
        cid = chats.save({"key": "a", "msgs": msgs})[0]["id"]
        got = chats.get({"id": cid})[0]
        self.assertEqual(len(got["msgs"]), chats.MAX_MSGS)
        self.assertEqual(got["msgs"][0]["role"], "user")                               # cut from the front, but it still starts with a question
        self.assertLessEqual(len(got["msgs"][-1]["code"]), chats.MAX_CODE)

    def test_a_cut_that_would_start_with_a_reply_drops_that_reply(self):
        msgs = [{"role": "user", "text": "first"}] + [{"role": "assistant" if i % 2 == 0 else "user", "text": f"m{i}"} for i in range(60)]
        cid = chats.save({"key": "a", "msgs": msgs})[0]["id"]
        self.assertEqual(chats.get({"id": cid})[0]["msgs"][0]["role"], "user")


if __name__ == "__main__":
    unittest.main()
