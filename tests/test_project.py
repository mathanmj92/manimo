import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import APP  # noqa: F401
import project
import server  # server.py wires project.configure(...) on import


class ProjectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="manimo-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(project.close)
        project.new("Lesson", self.tmp, starter=False, remember=False)
        self.root = project.current()

    def manifest(self):
        return json.loads((self.root / project.MANIFEST).read_text(encoding="utf-8"))

    def media(self, rel="assets/clip.mp4", data=b"x" * 10):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return rel


class New(ProjectCase):
    def test_layout(self):
        self.assertEqual(self.root.parent, self.tmp)
        for d in project.SUBDIRS:
            self.assertTrue((self.root / d).is_dir(), d)
        self.assertEqual(self.manifest()["timeline"]["size"], "auto")
        self.assertEqual(list((self.root / "scenes").glob("*.py")), [])

    def test_same_name_gets_numbered_folder(self):
        project.new("Lesson", self.tmp, starter=False, remember=False)
        self.assertEqual(project.current().name, "Lesson 2")

    def test_starter_has_a_scene(self):
        project.new("With starter", self.tmp, starter=True, remember=False)
        code = (project.current() / "scenes" / "intro.py").read_text(encoding="utf-8")
        self.assertEqual(server.find_scenes(code), ["Intro"])

    def test_reopen(self):
        project.close()
        self.assertIsNone(project.current())
        project.open_project(self.root, remember=False)
        self.assertEqual(project.current(), self.root)

    def test_open_non_project_fails(self):
        with self.assertRaises(ValueError):
            project.open_project(self.tmp, remember=False)

    def test_safe_name(self):
        self.assertEqual(project.safe_name("a/b:c*?"), "abc")
        self.assertEqual(project.safe_name("///"), "Untitled")


class Inside(ProjectCase):
    def test_inside_ok(self):
        self.assertEqual(project._inside("assets/a.mp4"), self.root / "assets" / "a.mp4")

    def test_dotdot_refused(self):
        self.assertIsNone(project._inside("../x.mp4"))
        self.assertIsNone(project._inside("assets/../../x.mp4"))

    def test_absolute_outside_refused(self):
        self.assertIsNone(project._inside(str(self.tmp.parent / "evil.mp4")))

    def test_no_project_open(self):
        project.close()
        self.assertIsNone(project._inside("a.mp4"))


class SceneHash(unittest.TestCase):
    base = {"quality": "m", "fps": 30, "encoding": "fast"}

    def h(self, code="x = 1", **kw):
        return project.scene_hash(code, "S", dict(self.base, **kw))

    def test_stable(self):
        self.assertEqual(self.h(), self.h())

    def test_shape_auto_or_missing_same_hash(self):
        self.assertEqual(self.h(), self.h(shape="auto"))
        self.assertEqual(self.h(), self.h(shape=None))

    def test_chosen_shape_changes_hash(self):
        self.assertNotEqual(self.h(), self.h(shape="9:16"))
        self.assertNotEqual(self.h(shape="9:16"), self.h(shape="1:1"))

    def test_speed_forms_equal_when_scene_speaks(self):
        code = "self.say('hi')"
        hashes = {self.h(code, voice="v", speed=s) for s in (1, 1.0, "1", "1.00")}
        self.assertEqual(len(hashes), 1)
        self.assertNotEqual(self.h(code, voice="v", speed=1), self.h(code, voice="v", speed=1.25))

    def test_speed_ignored_when_scene_silent(self):
        self.assertEqual(self.h(speed=1), self.h(speed=2))

    def test_code_scene_quality_change_hash(self):
        self.assertNotEqual(self.h(), self.h("x = 2"))
        self.assertNotEqual(self.h(), self.h(quality="h"))
        self.assertNotEqual(project.scene_hash("x", "A", self.base), project.scene_hash("x", "B", self.base))


class Timeline(ProjectCase):
    def test_bad_size_becomes_auto(self):
        for bad in ("5:5", "", None, 7, "16:9 "):
            project.set_timeline({"size": bad})
            self.assertEqual(self.manifest()["timeline"]["size"], "auto", bad)

    def test_good_sizes_kept(self):
        for good in project.SHAPES:
            project.set_timeline({"size": good})
            self.assertEqual(self.manifest()["timeline"]["size"], good)

    def test_paths_outside_project_dropped(self):
        ok = self.media()
        project.set_timeline({
            "clips": [{"src": ok}, {"src": "../evil.mp4"}, {"src": str(self.tmp.parent / "e.mp4")}],
            "audio": [{"src": ok}, {"src": "../../a.wav"}],
            "cams": [{"src": "../c.webm"}, {"src": ok}],
        })
        tl = self.manifest()["timeline"]
        self.assertEqual([c["src"] for c in tl["clips"]], [ok])
        self.assertEqual([a["src"] for a in tl["audio"]], [ok])
        self.assertEqual([c["src"] for c in tl["cams"]], [ok])

    def test_values_are_clamped(self):
        ok = self.media()
        project.set_timeline({
            "clips": [{"src": ok, "in": -5, "out": ""}],
            "audio": [{"src": ok, "volume": 9, "kind": "weird", "start": -1}],
            "cams": [{"src": ok, "corner": "zz", "size": 999}],
            "fps": 24,
        })
        tl = self.manifest()["timeline"]
        self.assertEqual(tl["clips"][0]["in"], 0.0)
        self.assertIsNone(tl["clips"][0]["out"])
        self.assertEqual(tl["audio"][0]["volume"], 2.0)
        self.assertEqual(tl["audio"][0]["kind"], "voice")
        self.assertEqual(tl["audio"][0]["start"], 0.0)
        self.assertEqual(tl["cams"][0]["corner"], "br")
        self.assertEqual(tl["cams"][0]["size"], 60)
        self.assertEqual(tl["fps"], 30)

    def test_fps_60(self):
        project.set_timeline({"fps": 60})
        self.assertEqual(self.manifest()["timeline"]["fps"], 60)


class EditVideo(ProjectCase):
    def test_missing_file_rejected(self):
        with self.assertRaises(ValueError):
            project.edit_video(self.tmp / "nope.mp4")

    def test_wrong_type_rejected(self):
        f = self.tmp / "notes.txt"
        f.write_text("hi")
        with self.assertRaises(ValueError):
            project.edit_video(f)

    def test_srt_rejected(self):
        f = self.tmp / "subs.srt"
        f.write_text("1")
        with self.assertRaises(ValueError):
            project.edit_video(f)

    def test_file_already_inside_is_used_in_place(self):
        rel = self.media("renders/a.mp4")
        st = project.edit_video(self.root / rel)
        self.assertEqual(st["src"], rel)
        self.assertFalse(st["quick"])

    def test_outside_video_is_imported(self):
        f = self.tmp / "outside.mp4"
        f.write_bytes(b"abc")
        st = project.edit_video(f)
        self.assertFalse(st["quick"])
        self.assertTrue((self.root / st["src"]).is_file())
        self.assertEqual((self.root / st["src"]).read_bytes(), b"abc")

    def test_quick_edit_without_project(self):
        f = self.tmp / "solo.mp4"
        f.write_bytes(b"abc")
        project.close()
        parent = self.tmp / "docs"
        orig = project.default_parent
        project.default_parent = lambda: parent
        self.addCleanup(setattr, project, "default_parent", orig)
        st = project.edit_video(f)
        self.assertTrue(st["quick"])
        self.assertEqual(project.current().parent.parent, parent)
        self.assertEqual((project.current() / st["src"]).read_bytes(), b"abc")


if __name__ == "__main__":
    unittest.main()
