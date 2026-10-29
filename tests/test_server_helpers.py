import unittest

from tests import APP  # noqa: F401  (sets sys.path)
import server


class VideoSize(unittest.TestCase):
    def test_default_is_16_9_at_each_quality(self):
        self.assertEqual(server.video_size("l", "16:9"), (854, 480))
        self.assertEqual(server.video_size("m", "16:9"), (1280, 720))
        self.assertEqual(server.video_size("h", "16:9"), (1920, 1080))
        self.assertEqual(server.video_size("k", "16:9"), (3840, 2160))

    def test_portrait_and_square(self):
        self.assertEqual(server.video_size("h", "9:16"), (1080, 1920))
        self.assertEqual(server.video_size("l", "9:16"), (480, 854))
        self.assertEqual(server.video_size("m", "1:1"), (720, 720))
        self.assertEqual(server.video_size("m", "4:3"), (960, 720))
        self.assertEqual(server.video_size("m", "3:4"), (720, 960))

    def test_all_shapes_have_even_sides_and_right_short_side(self):
        for q, short in server.SHORT_SIDE.items():
            for shape in server.SHAPES:
                w, h = server.video_size(q, shape)
                self.assertEqual((w % 2, h % 2), (0, 0), (q, shape))
                self.assertEqual(min(w, h), short, (q, shape))

    def test_auto_follows_code_else_16_9(self):
        code = "config.pixel_width, config.pixel_height = 1080, 1920"
        self.assertEqual(server.video_size("h", "auto", code), (1080, 1920))
        self.assertEqual(server.video_size("h", "auto", "print(1)"), (1920, 1080))
        self.assertEqual(server.video_size("h", "auto"), (1920, 1080))

    def test_explicit_shape_beats_code(self):
        code = "config.pixel_width, config.pixel_height = 1080, 1920"
        self.assertEqual(server.video_size("h", "1:1", code), (1080, 1080))

    def test_unknown_quality_falls_back_to_1080(self):
        self.assertEqual(server.video_size("zzz", "16:9"), (1920, 1080))

    def test_resolution_table(self):
        self.assertEqual(set(server.RESOLUTION), set(server.SHORT_SIDE))
        for q, text in server.RESOLUTION.items():
            self.assertEqual(tuple(map(int, text.split("x"))), server.video_size(q, "16:9"))

    def test_shapes_table_matches_project(self):
        import project
        self.assertEqual(server.SHAPES, project.SHAPES)
        self.assertEqual(set(server.SHAPES), {"16:9", "9:16", "1:1", "4:3", "3:4"})


class CodeShape(unittest.TestCase):
    def test_pair(self):
        self.assertEqual(server.code_shape("config.pixel_width, config.pixel_height = 1080, 1920"), (1080, 1920))

    def test_separate_lines(self):
        code = "config.pixel_width = 1000\nconfig.pixel_height = 500\n"
        self.assertEqual(server.code_shape(code), (1000, 500))

    def test_none(self):
        self.assertIsNone(server.code_shape(""))
        self.assertIsNone(server.code_shape(None))
        self.assertIsNone(server.code_shape("config.pixel_width = 1000"))


SAMPLE = '''import manimgx as m

class Intro(m.Scene):
    def construct(self):
        self.play(m.Create(m.Circle()))
        self.wait(1)

class Helper:
    pass

class Second(m.ThreeDScene, Mixin):
    def construct(self):
        self.play(a)
        self.play(b)
        self.wait()

class Third(manim.Scene):
    pass

class NotOne(Base):
    pass
'''


class Scenes(unittest.TestCase):
    def test_find_scenes(self):
        self.assertEqual(server.find_scenes(SAMPLE), ["Intro", "Second", "Third"])

    def test_find_scenes_empty(self):
        self.assertEqual(server.find_scenes("x = 1\n"), [])

    def test_scene_source_isolates_one_class(self):
        src = server.scene_source(SAMPLE, "Second")
        self.assertIn("class Second", src)
        self.assertNotIn("class Intro", src)
        self.assertNotIn("class Third", src)
        self.assertEqual(len(server.STEP_CALLS.findall(src)), 3)

    def test_scene_source_unknown_returns_all(self):
        self.assertEqual(server.scene_source(SAMPLE, "Nope"), SAMPLE)

    def test_result_and_error_regexes(self):
        m = server.RESULT.search("done: 1.0 s, 854x480 at 30 fps")
        self.assertEqual(m.groups(), ("1.0", "854x480", "30"))
        self.assertEqual(server.ERRLINE.search('File "scene.py", line 12').group(1), "12")
        self.assertEqual(server.ANSI.sub("", "\x1b[31mred\x1b[0m"), "red")


if __name__ == "__main__":
    unittest.main()
