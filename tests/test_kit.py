"""Phase 4: the lesson handout (PDF), GIF, share folder, brand kit, and the library's delete guard."""
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tests import APP  # noqa: F401  (sets sys.path)
import kit
import server

FF = server.ffmpeg_exe()
CODE = '''import manimgx as m


class Intro(m.Scene):
    def construct(self):
        self.say("A [block] on a slope.", m.Write(m.Text("x")))
        self.say("Friction is small.", m.FadeOut(m.Text("x")))
'''


def make_video(path, source="testsrc=size=320x180:rate=10", seconds=3):
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"{source}:d={seconds}" if ":d=" not in source else source,
                    "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono", "-shortest", "-pix_fmt", "yuv420p", str(path)], check=True, creationflags=0)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for p in (mock.patch.object(kit, "BRAND_FILE", self.dir / "brand.json"), mock.patch.dict(kit._deps, {"ffmpeg": lambda: FF, "timing": None}, clear=False)):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        with kit._lock:
            kit._job.clear()
            kit._job["state"] = "idle"


class Brand(Base):
    def test_a_brand_is_saved_trimmed_and_read_back(self):
        res, status = kit.brand_set({"name": "  Mrs   Rao  ", "tagline": "Physics, simply", "accent": "#112233"})
        self.assertEqual(status, 200)
        got = kit.brand_get()
        self.assertEqual((got["name"], got["tagline"], got["accent"]), ("Mrs Rao", "Physics, simply", "#112233"))

    def test_a_bad_colour_or_logo_is_refused_and_nothing_is_saved(self):
        self.assertEqual(kit.brand_set({"accent": "red"})[1], 400)
        self.assertEqual(kit.brand_set({"accent": "#12"})[1], 400)
        self.assertEqual(kit.brand_set({"logo": "data:text/html;base64,PHNjcmlwdD4="})[1], 400)
        self.assertEqual(kit.brand_set({"logo": "data:image/png;base64," + "A" * 700_000})[1], 400)
        self.assertEqual(kit.brand_get(), kit.DEFAULT_BRAND)

    def test_a_small_png_logo_is_accepted(self):
        logo = "data:image/png;base64,iVBORw0KGgo="
        self.assertEqual(kit.brand_set({"logo": logo})[1], 200)
        self.assertEqual(kit.brand_get()["logo"], logo)

    def test_a_damaged_brand_file_gives_the_defaults(self):
        (self.dir / "brand.json").write_text("{nope", encoding="utf-8")
        self.assertEqual(kit.brand_get(), kit.DEFAULT_BRAND)


class Solution(unittest.TestCase):
    def test_a_solved_problem_is_split_by_its_labels(self):
        parts = kit.parse_solution("Given: m = 10 kg.\nFind: a.\nMethod: Newton.\nSteps:\n1. one\n2. two\nAnswer: 2.78\nCheck: ok")
        self.assertEqual([p[0] for p in parts], ["Given", "Find", "Method", "Steps", "Answer", "Check"])
        self.assertEqual(parts[3][1], "1. one\n2. two")

    def test_text_without_labels_stays_whole_and_empty_gives_nothing(self):
        self.assertEqual(kit.parse_solution("Just some working out."), [("", "Just some working out.")])
        self.assertEqual(kit.parse_solution("   "), [])

    def test_bold_labels_from_an_assistant_reply_are_understood(self):
        self.assertEqual([p[0] for p in kit.parse_solution("**Given:** a\n**Answer:** b")], ["Given", "Answer"])


class Frames(unittest.TestCase):
    def test_each_spoken_line_gets_the_stretch_before_the_next_one_starts(self):
        timing = {"lines": [{"t": 0.0}, {"t": 4.0}], "end": 9.0}
        self.assertEqual(kit.frame_windows(2, 9.0, timing), [(0.0, 3.9), (4.0, 8.9)])

    def test_without_timing_the_lines_share_the_video_evenly(self):
        w = kit.frame_windows(3, 9.0, None)
        self.assertEqual(len(w), 3)
        self.assertEqual(w[0][0], 0.0)
        self.assertLess(w[0][1], w[1][0] + 0.5)
        self.assertEqual(kit.frame_windows(0, 9.0, None), [])

    @unittest.skipUnless(FF, "ffmpeg is not available")
    def test_a_blank_picture_is_skipped_and_one_with_content_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            black, busy = Path(d) / "black.mp4", Path(d) / "busy.mp4"
            make_video(black, "color=c=black:size=320x180:rate=10")
            make_video(busy)
            self.assertIsNone(kit.best_frame(FF, black, 0.2, 2.0, 640))
            got = kit.best_frame(FF, busy, 0.2, 2.0, 640)
            self.assertTrue(got and got[:2] == b"\xff\xd8")                   # a JPEG
            self.assertGreater(kit.duration(FF, busy), 2.5)

    @unittest.skipUnless(FF, "ffmpeg is not available")
    def test_the_printing_version_has_a_light_background(self):
        with tempfile.TemporaryDirectory() as d:
            black = Path(d) / "black.mp4"
            make_video(black, "color=c=black:size=320x180:rate=10")
            dark, light = kit.frame(FF, black, 0.5, 320, False), kit.frame(FF, black, 0.5, 320, True)
        self.assertNotEqual(dark, light)


class Readability(unittest.TestCase):
    def test_contrast_is_the_standard_ratio(self):
        self.assertAlmostEqual(kit.contrast("#000000"), 21.0, places=1)
        self.assertAlmostEqual(kit.contrast("#ffffff"), 1.0, places=1)

    def test_a_pale_accent_is_darkened_until_text_in_it_can_be_read_and_a_dark_one_is_kept(self):
        for pale in ("#f2c200", "#7bd389", "#ffff00", "#ffd0d0"):
            self.assertGreaterEqual(kit.contrast(kit.readable_accent(pale)), 4.5, pale)
        self.assertEqual(kit.readable_accent("#1e3a8a"), "#1e3a8a")

    def test_the_page_uses_the_readable_colour_for_text_and_the_real_one_for_borders(self):
        page = kit.lesson_html({"title": "T", "brand": {"accent": "#f2c200"}, "sections": [], "date": "", "audience": ""})
        self.assertIn("--accent:#f2c200", page)
        self.assertNotIn("--accent-text:#f2c200", page)

    def test_the_footer_text_colour_is_dark_enough(self):
        self.assertGreaterEqual(kit.contrast("#4d576b"), 7.0)


class FramePicking(unittest.TestCase):
    """best_frame chooses by how much is on each picture (its JPEG size); this feeds it made-up sizes."""

    def pick(self, sizes, limit=None, lo=0.0, hi=8.0):
        calls = []

        def fake(ff, video, t, width=960, light=False):
            calls.append(t)
            i = min(range(len(sizes)), key=lambda k: abs(k * (hi - lo) / 4 - (t - lo)))
            return None if sizes[i] is None else bytes([i]) * sizes[i]
        with mock.patch.object(kit, "frame", fake):
            got = kit.best_frame("ff", "v", lo, hi, limit=limit)
        return (got[0] if got else None), calls

    def test_the_latest_complete_picture_wins(self):
        self.assertEqual(self.pick([6000, 8000, 10000, 12000, 12500])[0], 4)          # the step is finished by the end

    def test_a_fade_out_at_the_end_does_not_win(self):
        self.assertEqual(self.pick([6000, 9000, 13000, 12500, 4000])[0], 3)           # the last moment is nearly empty: the latest full one is used

    def test_a_picture_that_cannot_be_read_is_skipped_rather_than_ending_in_an_older_one_by_accident(self):
        self.assertEqual(self.pick([6000, 9000, 13000, 13200, None])[0], 3)

    def test_blank_stretches_give_no_picture_at_all(self):
        self.assertIsNone(self.pick([2500, 2500, 2500, 2500, 2500])[0])
        self.assertIsNone(self.pick([None, None, None, None, None])[0])

    def test_no_moment_is_taken_beyond_the_end_of_the_video(self):
        _, calls = self.pick([9000, 9000, 9000, 9000, 9000], limit=7.0)
        self.assertLessEqual(max(calls), 6.7 + 1e-9)


class Handout(Base):
    def data(self, **kw):
        d = {"title": "Block on an incline", "audience": "Class 11", "date": "1 January 2026", "problem": "Find a.", "solution": "Given: m.\nAnswer: 2.78",
             "figure": None, "sections": [{"name": "Intro", "steps": [{"text": "A block.", "frame": b"\xff\xd8\xff\xd9"}, {"text": "No picture.", "frame": None}]}, {"name": "Empty", "steps": []}],
             "brand": kit.brand_get()}
        d.update(kw)
        return d

    def test_the_page_has_the_problem_the_solution_and_the_steps_and_says_manimo_in_the_footer_not_on_a_page_of_its_own(self):
        page = kit.lesson_html(self.data())
        for part in ("Block on an incline", "PROBLEM", "Find a.", "<dt>Given</dt>", "Answer: 2.78", "A block.", "No picture.", "This scene has no narration", "data:image/jpeg;base64,"):
            self.assertIn(part, page)
        self.assertNotIn("brand-end", page)                                            # no closing brand page
        self.assertIn("@bottom-left", page)
        self.assertIn('--footer-text:"Made with Manimo · mathanmj92.github.io/manimo-site"', page)

    def test_the_footer_names_the_teacher_too_and_quotes_in_names_cannot_break_out(self):
        kit.brand_set({"name": 'Mrs "Rao" \\ School'})
        page = kit.lesson_html(self.data())
        self.assertIn('Prepared by Mrs \\"Rao\\" \\\\ School · Made with Manimo', page)

    def test_large_pictures_run_across_the_page_and_compact_ones_sit_beside_their_text(self):
        self.assertIn('class="step big"', kit.lesson_html(self.data()))
        self.assertIn('class="step side"', kit.lesson_html(self.data(size="compact")))

    def test_large_print_makes_the_type_bigger(self):
        self.assertIn("--base:11pt", kit.lesson_html(self.data()))
        self.assertIn("--base:13pt", kit.lesson_html(self.data(large_print=True)))

    def test_nothing_typed_by_the_teacher_can_inject_markup(self):
        page = kit.lesson_html(self.data(title="<script>alert(1)</script>", problem="<img src=x onerror=alert(1)>", sections=[{"name": "<b>x</b>", "steps": [{"text": "<i>y</i>", "frame": None}]}]))
        for bad in ("<script>alert", "<img src=x", "<b>x</b>", "<i>y</i>"):
            self.assertNotIn(bad, page)
        self.assertIn("&lt;script&gt;", page)

    def test_the_teachers_brand_is_at_the_top_and_in_the_colours(self):
        kit.brand_set({"name": "Mrs Rao", "accent": "#aa3300", "logo": "data:image/png;base64,iVBORw0KGgo="})
        page = kit.lesson_html(self.data())
        self.assertIn("Mrs Rao", page)
        self.assertIn("--accent:#aa3300", page)
        self.assertIn("Prepared by Mrs Rao · Made with Manimo", page)
        self.assertEqual(page.count("data:image/png;base64,iVBORw0KGgo="), 1)       # the logo at the top of the first page

    @unittest.skipUnless(kit.find_edge(), "Edge is not available")
    def test_the_page_prints_to_a_real_pdf_with_the_footer_on_the_page(self):
        html_path, pdf = self.dir / "h.html", self.dir / "h.pdf"
        html_path.write_text(kit.lesson_html(self.data()), encoding="utf-8")
        self.assertTrue(kit.html_to_pdf(html_path, pdf))
        self.assertEqual(pdf.read_bytes()[:5], b"%PDF-")
        self.assertGreaterEqual(kit._pdf_pages(pdf), 1)

    @unittest.skipUnless(kit.find_edge(), "Edge is not available")
    def test_the_whole_job_works_without_any_videos_and_says_which_scenes_have_none(self):
        body = {"code": CODE, "out_dir": str(self.dir), "title": "Lesson one", "frames": "lines", "scenes": [{"name": "Intro", "video": ""}], "problem": "P", "solution": "Answer: 1"}
        self.assertEqual(kit._start("pdf", kit.build_handout, body)[1], 200)
        for _ in range(120):
            if kit.job()["state"] != "running":
                break
            time.sleep(0.25)
        j = kit.job()
        self.assertEqual(j["state"], "done", j)
        self.assertEqual(j["kind"], "pdf")
        self.assertEqual(j["missing"], ["Intro"])
        self.assertTrue(Path(j["file"]).is_file())
        self.assertFalse(list(self.dir.glob("*.html")))                                # the temporary web page is removed once the PDF exists

    def test_only_one_export_runs_at_a_time(self):
        with kit._lock:
            kit._job["state"] = "running"
        self.assertEqual(kit._start("pdf", kit.build_handout, {})[1], 409)


@unittest.skipUnless(FF, "ffmpeg is not available")
class GifAndShare(Base):
    def setUp(self):
        super().setUp()
        self.a, self.b = self.dir / "Intro.mp4", self.dir / "Solve.mp4"
        make_video(self.a)
        make_video(self.b)

    def run_job(self, fn, body):
        self.assertEqual(kit._start("x", fn, body)[1], 200)
        for _ in range(240):
            if kit.job()["state"] != "running":
                break
            time.sleep(0.25)
        return kit.job()

    def test_a_gif_is_made_from_a_scene_found_by_name_in_the_output_folder(self):
        j = self.run_job(kit.build_gif, {"out_dir": str(self.dir), "scene": "Solve", "seconds": 2, "width": 240})
        self.assertEqual(j["state"], "done", j)
        self.assertEqual(Path(j["file"]).read_bytes()[:6], b"GIF89a")

    def test_a_gif_of_a_scene_with_no_video_says_to_render_it(self):
        j = self.run_job(kit.build_gif, {"out_dir": str(self.dir), "scene": "Nope"})
        self.assertEqual(j["state"], "error")
        self.assertIn("Render the scene", j["error"])

    def test_the_share_folder_joins_the_scenes_and_lists_chapter_times(self):
        j = self.run_job(kit.build_share, {"out_dir": str(self.dir), "title": "Block lesson", "description": "A worked example.",
                                           "scenes": [{"name": "Intro", "video": ""}, {"name": "Solve", "video": ""}]})
        self.assertEqual(j["state"], "done", j)
        folder = Path(j["file"])
        self.assertEqual(sorted(j["files"]), ["Block_lesson.mp4", "chapters.txt", "cover.jpg", "description.txt", "title.txt"])
        self.assertAlmostEqual(kit.duration(FF, folder / "Block_lesson.mp4"), 6.0, delta=0.6)
        lines = (folder / "chapters.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, ["0:00 Intro", "0:03 Solve"])
        self.assertIn("A worked example.", (folder / "description.txt").read_text(encoding="utf-8"))


class LibraryDelete(unittest.TestCase):
    def test_only_videos_inside_the_chosen_folder_can_be_deleted(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as other:
            keep, note, outside = Path(d) / "notes.txt", Path(d) / ".hidden.mp4", Path(other) / "x.mp4"
            for f in (keep, note, outside):
                f.write_text("x", encoding="utf-8")
            for paths in ([str(keep)], [str(note)], [str(outside)], [], [str(Path(d) / "gone.mp4")]):
                self.assertEqual(server.library_delete({"dir": d, "paths": paths})[1], 400, paths)
            self.assertTrue(keep.exists() and note.exists() and outside.exists())


if __name__ == "__main__":
    unittest.main()
