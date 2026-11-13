"""The PowerPoint export: a valid package, the right slides, the narration in the notes, and Manimo in every footer (not on a slide of its own)."""
import posixpath
import re
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

from tests import APP  # noqa: F401  (sets sys.path)
import kit
import pptx_writer
import server

FF = server.ffmpeg_exe()
CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
RELS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def real_jpeg():
    if FF:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "f.jpg"
            subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=1:d=1", "-frames:v", "1", str(out)], check=True)
            return out.read_bytes()
    return b"\xff\xd8\xff\xc0\x00\x0b\x08\x01\x68\x02\x80\x01\x01\x11\x00\xff\xd9"       # a bare header that says 640 x 360


JPEG = real_jpeg()


def data(**kw):
    d = {"title": "Block on an incline", "audience": "Class 11", "date": "1 January 2026", "problem": "Find a.", "figure": JPEG,
         "solution": "Given: m = 10 kg.\nFind: a.\nMethod: Newton.\nSteps:\n1. one\n2. two\nAnswer: 2.78\nCheck: ok",
         "sections": [{"name": "Setup", "narration": "First line. Second line.", "steps": [{"text": "First line.", "frame": JPEG}, {"text": "Second line.", "frame": JPEG}]},
                      {"name": "Quiet", "narration": "", "steps": []}],
         "brand": {"name": "", "tagline": "", "accent": "#1fa5bd", "logo": ""}, "size": "large", "large_print": False}
    d.update(kw)
    return d


class Writer(unittest.TestCase):
    def build(self, slides, **deck):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "d.pptx"
        pptx_writer.build(path, {"title": "T", "footer": "Made with Manimo · site", "accent": "167688", "slides": slides, **deck})
        return zipfile.ZipFile(path)

    def slides(self):
        return [{"layout": "title", "title": "Title", "caption": "sub", "notes": ""}, {"layout": "text", "title": "Text", "paras": [("hello", False, None), ("Label", True, "167688")], "notes": "say it"},
                {"layout": "picture", "title": "Pic", "image": JPEG, "image_alt": 'A "quoted" <alt>', "caption": "Caption", "notes": "line one\nline two"},
                {"layout": "textpicture", "title": "Both", "image": JPEG, "paras": [("text", False, None)], "notes": ""}]

    def test_every_part_is_well_formed_and_every_relationship_points_at_a_real_part(self):
        z = self.build(self.slides())
        names = set(z.namelist())
        for n in names:
            if n.endswith((".xml", ".rels")):
                ET.fromstring(z.read(n))                                              # raises when a part is not well-formed XML
        for n in [x for x in names if x.endswith(".rels")]:
            base = posixpath.dirname(posixpath.dirname(n))
            for rel in ET.fromstring(z.read(n)).findall(RELS + "Relationship"):
                target = posixpath.normpath(posixpath.join(base, rel.get("Target")))
                self.assertIn(target, names, f"{n} points at {target}")

    def test_every_part_has_a_content_type_and_the_package_has_what_powerpoint_needs(self):
        z = self.build(self.slides())
        ct = ET.fromstring(z.read("[Content_Types].xml"))
        overrides = {o.get("PartName") for o in ct.findall(CT + "Override")}
        defaults = {d.get("Extension") for d in ct.findall(CT + "Default")}
        for n in z.namelist():
            if n == "[Content_Types].xml":
                continue
            self.assertTrue(("/" + n) in overrides or n.rsplit(".", 1)[-1] in defaults, n)
        for need in ("ppt/presentation.xml", "ppt/slideMasters/slideMaster1.xml", "ppt/slideLayouts/slideLayout1.xml", "ppt/theme/theme1.xml", "ppt/notesMasters/notesMaster1.xml"):
            self.assertIn(need, z.namelist())

    def test_four_slides_with_notes_a_picture_each_where_asked_and_the_footer_on_every_one(self):
        z = self.build(self.slides())
        for i in range(1, 5):
            slide = z.read(f"ppt/slides/slide{i}.xml").decode("utf-8")
            self.assertIn("Made with Manimo · site", slide)
            self.assertIn(f"notesSlide{i}.xml", z.read(f"ppt/slides/_rels/slide{i}.xml.rels").decode("utf-8"))
        self.assertEqual(len([n for n in z.namelist() if n.startswith("ppt/media/")]), 2)
        self.assertIn("line one", z.read("ppt/notesSlides/notesSlide3.xml").decode("utf-8"))
        self.assertIn("line two", z.read("ppt/notesSlides/notesSlide3.xml").decode("utf-8"))

    def test_text_is_escaped_and_pictures_carry_alt_text(self):
        slide = self.build(self.slides() + [{"layout": "text", "title": "<b>&", "paras": [("a < b & c", False, None)], "notes": ""}]).read("ppt/slides/slide5.xml").decode("utf-8")
        self.assertNotIn("<b>&", slide)
        self.assertIn("a &lt; b &amp; c", slide)
        z = self.build(self.slides())
        self.assertIn('descr="A &quot;quoted&quot; &lt;alt&gt;"', z.read("ppt/slides/slide3.xml").decode("utf-8"))

    def test_a_picture_is_fitted_inside_its_box_without_being_stretched(self):
        self.assertEqual(pptx_writer.jpeg_size(JPEG), (640, 360))
        w, h = pptx_writer._fit((640, 360), 8000000, 3000000)
        self.assertEqual(h, 3000000)
        self.assertAlmostEqual(w / h, 640 / 360, places=2)
        self.assertIsNone(pptx_writer.jpeg_size(b"not a jpeg"))

    def test_the_text_on_a_slide_is_big_enough_to_read_from_the_back_of_a_room(self):
        slide = self.build(self.slides()).read("ppt/slides/slide2.xml").decode("utf-8")
        sizes = {int(s) for s in re.findall(r'sz="(\d+)"', slide)}
        self.assertTrue(all(s >= 1100 for s in sizes), sizes)                          # the footer is the smallest thing on the slide, at 11 pt
        self.assertIn(2400, sizes)


class Deck(unittest.TestCase):
    def test_the_deck_opens_with_a_title_then_the_problem_with_its_figure_then_the_solution_then_a_slide_for_each_spoken_line(self):
        slides, _ = kit.deck_slides(data())
        self.assertEqual([s["title"] for s in slides][:2], ["Block on an incline", "Problem"])
        self.assertEqual(slides[1]["layout"], "textpicture")
        titles = [s["title"] for s in slides]
        self.assertEqual(titles[2:4], ["Solution (1 of 2)", "Solution (2 of 2)"])
        self.assertEqual(titles[4:], ["Setup: step 1", "Setup: step 2", "Quiet"])
        self.assertTrue(all(s["layout"] == "picture" for s in slides if s["title"].startswith("Setup")))

    def test_the_whole_scene_is_in_the_notes_of_each_step_and_the_quiet_scene_says_so(self):
        slides, _ = kit.deck_slides(data())
        step = next(s for s in slides if s["title"] == "Setup: step 2")
        self.assertIn("Step 2: Second line.", step["notes"])
        self.assertIn("First line. Second line.", step["notes"])
        self.assertIn("no narration", next(s for s in slides if s["title"] == "Quiet")["paras"][0][0])

    def test_one_slide_for_each_scene_uses_its_finished_picture(self):
        slides, _ = kit.deck_slides(data(), per_scene=True)
        scenes = [s for s in slides if s["title"] in ("Setup", "Quiet")]
        self.assertEqual([s["layout"] for s in scenes], ["picture", "text"])
        self.assertEqual(scenes[0]["notes"], "First line. Second line.")

    def test_the_solution_is_split_so_no_slide_is_a_wall_of_text(self):
        slides, accent = kit.deck_slides(data())
        sol = [s for s in slides if s["title"].startswith("Solution")]
        self.assertEqual(len(sol), 2)
        self.assertIn("Given", [p[0] for p in sol[0]["paras"]])
        self.assertIn("Steps", [p[0] for p in sol[1]["paras"]])
        self.assertTrue(any(p[1] and p[0].startswith("2.78") for p in sol[1]["paras"]))     # the answer is bold
        self.assertRegex(accent, r"^[0-9A-F]{6}$")

    def test_no_problem_and_no_solution_leave_just_the_title_and_the_scenes(self):
        slides, _ = kit.deck_slides(data(problem="", solution="", figure=None))
        self.assertEqual([s["title"] for s in slides], ["Block on an incline", "Setup: step 1", "Setup: step 2", "Quiet"])

    def test_nothing_is_added_at_the_end_for_the_brand(self):
        slides, _ = kit.deck_slides(data())
        self.assertNotIn("Manimo", slides[-1]["title"])


class Job(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        with kit._lock:
            kit._job.clear()
            kit._job["state"] = "idle"
        p = mock.patch.object(kit, "collect_lesson", lambda body: dict(data(), out_dir=Path(self.tmp.name), missing=["Quiet"], blank=["Setup, step 2"]))
        p.start()
        self.addCleanup(p.stop)

    def run_job(self, body):
        self.assertEqual(kit.handle("POST", "/api/kit/pptx", body)[1], 200)
        for _ in range(100):
            if kit.job()["state"] != "running":
                break
            time.sleep(0.1)
        return kit.job()

    def test_the_job_writes_a_deck_and_reports_what_was_missing(self):
        j = self.run_job({})
        self.assertEqual(j["state"], "done", j)
        self.assertEqual((j["kind"], j["missing"], j["blank"]), ("pptx", ["Quiet"], ["Setup, step 2"]))
        self.assertGreater(j["slides"], 5)
        z = zipfile.ZipFile(j["file"])
        self.assertIn("ppt/presentation.xml", z.namelist())
        self.assertIn("Made with Manimo · mathanmj92.github.io/manimo-site", z.read("ppt/slides/slide1.xml").decode("utf-8"))

    def test_the_slides_option_chooses_one_slide_for_each_scene(self):
        self.assertEqual(self.run_job({"slides": "scene"})["slides"], 1 + 1 + 2 + 2)           # title, problem, two solution slides, two scenes

    def test_the_route_is_registered_with_the_server(self):
        self.assertIn("/api/kit/pptx", Path(server.__file__).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
