"""The assistant's cheaper habits: read a picture once, solve first, show an estimate, and survive a model name the agent does not know."""
import base64
import io
import json
import unittest
from unittest import mock

from tests import APP  # noqa: F401  (sets sys.path)
import ai

PROBLEM = "Solve this problem: a 10 kg block slides down a rough incline of 30 degrees, mu = 0.25. Find the acceleration."
TINY_JPEG = base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 200).decode()


class SolveFirst(unittest.TestCase):
    def test_a_new_problem_is_solved_first_when_the_switch_is_on(self):
        self.assertTrue(ai.wants_solve_first({"prompt": PROBLEM, "solve_first": True}, "write"))
        self.assertTrue(ai.wants_solve_first({"prompt": PROBLEM, "solve_first": True}, "edit"))

    def test_not_when_off_when_short_when_an_edit_or_when_not_a_problem(self):
        self.assertFalse(ai.wants_solve_first({"prompt": PROBLEM, "solve_first": False}, "write"))
        self.assertFalse(ai.wants_solve_first({"prompt": "solve it", "solve_first": True}, "write"))
        self.assertFalse(ai.wants_solve_first({"prompt": "Fix the problem with the beam label so it does not overlap the arrow", "solve_first": True}, "write"))
        self.assertFalse(ai.wants_solve_first({"prompt": "Animate the Pythagorean theorem with squares on the three sides", "solve_first": True}, "write"))
        self.assertFalse(ai.wants_solve_first({"prompt": PROBLEM, "solve_first": True}, "explain"))

    def test_the_solve_prompt_is_small_and_has_no_animation_stages(self):
        p = ai.solve_prompt()
        self.assertLess(len(p) // 4, 3000)
        self.assertIn("Given:", p)
        self.assertNotIn("Stage 4", p)

    def test_the_run_uses_the_solve_prompt_and_a_small_reply_limit(self):
        seen = {}

        def fake_stream(cfg, system, messages, on_delta, max_tokens=ai.MAX_TOKENS):
            seen.update(system=system, max_tokens=max_tokens, last=messages[-1]["content"])
            on_delta("Given: 10 kg\nAnswer: 3.0 m/s^2")
        with mock.patch.object(ai, "stream", fake_stream), mock.patch.object(ai, "load_settings", lambda: {"provider": "agent", "agent": "claude"}):
            ai._job.clear()
            ai._job.update({"state": "running", "steps": [], "text": "", "final": None, "error": None})
            ai.run({"prompt": PROBLEM, "mode": "write", "solve_first": True, "code": "import manimgx as m", "use_code": True, "history": []})
        self.assertEqual(ai._job["state"], "done")
        self.assertEqual(ai._job["final"]["kind"], "solve")
        self.assertEqual(ai._job["final"]["code"], "")
        self.assertEqual(seen["max_tokens"], 2200)
        self.assertEqual(seen["system"], ai.solve_prompt())
        self.assertNotIn("current_code", seen["last"])        # the editor's code is not sent for a solve step


LESSON = "Teach how a capacitor charges through a resistor, for first-year students, with a worked example"


class PlanFirst(unittest.TestCase):
    def test_a_new_lesson_is_planned_first_when_the_switch_is_on(self):
        self.assertTrue(ai.wants_plan_first({"prompt": LESSON, "plan_first": True}, "write"))
        self.assertFalse(ai.wants_plan_first({"prompt": LESSON, "plan_first": False}, "write"))

    def test_not_for_edits_short_requests_or_other_modes(self):
        self.assertFalse(ai.wants_plan_first({"prompt": "Make the circle bigger and slower in the second scene please", "plan_first": True}, "write"))
        self.assertFalse(ai.wants_plan_first({"prompt": "capacitors", "plan_first": True}, "write"))
        self.assertFalse(ai.wants_plan_first({"prompt": LESSON, "plan_first": True}, "explain"))

    def test_a_problem_is_solved_first_not_planned(self):
        req = {"prompt": PROBLEM, "solve_first": True, "plan_first": True}
        self.assertTrue(ai.wants_solve_first(req, "write"))
        self.assertFalse(ai.wants_plan_first(req, "write"))

    def test_the_plan_is_text_only_with_its_own_small_prompt(self):
        seen = {}

        def fake_stream(cfg, system, messages, on_delta, max_tokens=ai.MAX_TOKENS):
            seen.update(system=system, max_tokens=max_tokens, last=messages[-1]["content"])
            on_delta("Title: Charging\nScenes:\n1. The circuit - a battery, a switch, R and C. Narration: Here is the circuit.")
        with mock.patch.object(ai, "stream", fake_stream), mock.patch.object(ai, "load_settings", lambda: {"provider": "agent", "agent": "claude"}):
            ai._job.clear()
            ai._job.update({"state": "running", "steps": [], "text": "", "final": None, "error": None})
            ai.run({"prompt": LESSON, "mode": "write", "plan_first": True, "code": "import manimgx as m", "use_code": True, "history": []})
        self.assertEqual(ai._job["state"], "done")
        self.assertEqual(ai._job["final"]["kind"], "plan")
        self.assertEqual(ai._job["final"]["code"], "")
        self.assertEqual(seen["system"], ai.plan_prompt())
        self.assertEqual(seen["max_tokens"], 1800)
        self.assertNotIn("current_code", seen["last"])
        self.assertLess(len(ai.plan_prompt()) // 4, 400)

    def test_the_estimate_says_a_plan_is_the_cheap_step(self):
        full, _ = ai.estimate({"prompt": LESSON, "plan_first": False, "solve_first": False})
        plan, _ = ai.estimate({"prompt": LESSON, "plan_first": True, "solve_first": False})
        self.assertTrue(plan["plan_first"])
        self.assertEqual(plan["rounds"], 1)
        self.assertLess(plan["tokens"] * 3, full["tokens"])


class Estimate(unittest.TestCase):
    def test_solving_first_is_much_cheaper_than_the_full_request(self):
        full, _ = ai.estimate({"prompt": PROBLEM, "solve_first": False})
        first, _ = ai.estimate({"prompt": PROBLEM, "solve_first": True})
        self.assertTrue(first["solve_first"])
        self.assertFalse(full["solve_first"])
        self.assertLess(first["tokens"] * 3, full["tokens"])
        self.assertEqual(first["rounds"], 1)

    def test_code_and_chat_count(self):
        base, _ = ai.estimate({"prompt": "animate a circle growing", "solve_first": False})
        more, _ = ai.estimate({"prompt": "animate a circle growing", "solve_first": False, "use_code": True, "code": "x = 1\n" * 4000,
                               "history": [{"role": "user", "text": "hello " * 500}]})
        self.assertGreater(more["tokens"], base["tokens"] + 1000)


class ReadPicture(unittest.TestCase):
    def setUp(self):
        self.cfg = mock.patch.object(ai, "load_settings", lambda: {"provider": "agent", "agent": "claude"})
        self.cfg.start()
        ai._job.clear()

    def tearDown(self):
        self.cfg.stop()

    def test_the_picture_goes_with_a_short_system_prompt_and_no_history(self):
        seen = {}

        def fake(cfg, system, messages, on_delta, max_tokens=0):
            seen.update(system=system, messages=messages, max_tokens=max_tokens)
            on_delta("Problem: a block on an incline.\nGiven: 10 kg")
        with mock.patch.object(ai, "stream", fake):
            res, status = ai.read_image({"image": "data:image/jpeg;base64," + TINY_JPEG})
        self.assertEqual(status, 200)
        self.assertIn("Given", res["text"])
        self.assertEqual(seen["system"], ai.READ_SYSTEM)
        self.assertLess(len(ai.READ_SYSTEM) // 4, 400)
        self.assertEqual(seen["max_tokens"], 900)
        self.assertEqual(len(seen["messages"]), 1)
        self.assertEqual(seen["messages"][0]["content"][0]["type"], "image")

    def test_refuses_nothing_or_too_much(self):
        self.assertEqual(ai.read_image({})[1], 400)
        self.assertEqual(ai.read_image({"image": "A" * (ai.MAX_IMAGE_B64 + 1)})[1], 400)

    def test_provider_errors_come_back_as_plain_messages(self):
        def boom(*a, **k):
            raise ai.AIError("Could not reach the AI provider.")
        with mock.patch.object(ai, "stream", boom):
            res, status = ai.read_image({"image": TINY_JPEG})
        self.assertEqual(status, 502)
        self.assertIn("provider", res["error"])


class Providers(unittest.TestCase):
    def test_openai_style_services_get_the_picture_in_their_own_format(self):
        sent = {}

        class Resp:
            def __iter__(self):
                return iter([b"data: [DONE]\n"])

            def close(self):
                pass

        def fake_open(req, timeout=90):
            sent["body"] = json.loads(req.data.decode())
            return Resp()
        msgs = [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}},
                                             {"type": "text", "text": "read it"}]}]
        with mock.patch.object(ai, "_open", fake_open), mock.patch.object(ai, "api_key", lambda c: "k"):
            ai.stream_openai({"model": "m", "base_url": "http://x/v1"}, "sys", msgs, lambda p: None, 100)
        parts = sent["body"]["messages"][1]["content"]
        self.assertEqual(parts[0]["type"], "image_url")
        self.assertTrue(parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(parts[1], {"type": "text", "text": "read it"})

    def test_an_unknown_saved_model_name_falls_back_to_the_agents_default(self):
        calls = []

        def fake(cfg, system, messages, on_delta, max_tokens=0):
            calls.append(cfg.get("agent_model"))
            if cfg.get("agent_model"):
                raise ai.AIError("Claude Code stopped with an error. There's an issue with the selected model (sonnet5.5).")
            on_delta("ok")
        out = []
        with mock.patch.object(ai, "_stream_once", fake):
            ai.stream({"provider": "agent", "agent": "claude", "agent_model": "sonnet5.5"}, "s", [], out.append, 10)
        self.assertEqual(calls, ["sonnet5.5", ""])
        self.assertEqual(out, ["ok"])

    def test_other_errors_are_not_retried(self):
        def fake(cfg, system, messages, on_delta, max_tokens=0):
            raise ai.AIError("The API key was rejected.")
        with mock.patch.object(ai, "_stream_once", fake):
            with self.assertRaises(ai.AIError):
                ai.stream({"provider": "anthropic", "model": "m"}, "s", [], lambda p: None, 10)

    def test_the_agent_only_gets_the_picture_when_a_message_holds_one(self):
        self.assertEqual(ai._agent_images([{"role": "user", "content": "text only"}]), [])
        img = {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}}
        self.assertEqual(ai._agent_images([{"role": "user", "content": [img, {"type": "text", "text": "x"}]}]), [img])


class WindowButtons(unittest.TestCase):
    def test_only_known_actions_reach_the_window(self):
        import server
        seen = []
        server.HOOKS["window"].append(seen.append)
        try:
            self.assertEqual(server.window_action({"action": "max"})[1], 200)
            self.assertEqual(server.window_action({"action": "format c:"})[1], 400)
            self.assertEqual(server.window_action({})[1], 400)
        finally:
            server.HOOKS["window"].remove(seen.append)
        self.assertEqual(seen, ["max"])


if __name__ == "__main__":
    unittest.main()
