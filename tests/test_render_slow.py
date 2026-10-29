import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import APP  # noqa: F401
import server

SLOW = os.environ.get("MANIMO_SLOW") == "1"

SCENE = '''import manimgx as m

class Dot(m.Scene):
    def construct(self):
        c = m.Circle()
        self.play(m.Create(c), run_time=0.5)
        self.wait(0.5)
'''


def ffmpeg_info(path):
    import imageio_ffmpeg
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    text = r.stderr
    size = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", text)
    d = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    secs = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0
    return (int(size.group(1)), int(size.group(2))) if size else None, secs


@unittest.skipUnless(SLOW, "slow: set MANIMO_SLOW=1 to render real videos")
class RenderEndToEnd(unittest.TestCase):
    """SLOW: runs the real `python -m manimgx render` command and checks the MP4 it writes."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="manimo-render-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "scene.py").write_text(SCENE, encoding="utf-8")

    def render(self, size, name):
        out = self.tmp / f"{name}.mp4"
        cmd = [sys.executable, "-m", "manimgx", "render", str(self.tmp / "scene.py"), "Dot",
               "-o", str(out), "-r", f"{size[0]}x{size[1]}", "--fps", "15", "--preset", "ultrafast"]
        r = subprocess.run(cmd, cwd=self.tmp, capture_output=True, text=True, timeout=600,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(out.is_file() and out.stat().st_size > 1000)
        return ffmpeg_info(out)

    def test_landscape_480p(self):
        size = server.video_size("l", "16:9")
        dims, secs = self.render(size, "wide")
        self.assertEqual(dims, size)
        self.assertAlmostEqual(secs, 1.0, delta=0.3)

    def test_tall_9_16(self):
        size = server.video_size("l", "9:16")
        dims, secs = self.render(size, "tall")
        self.assertEqual(dims, size)
        self.assertEqual(dims, (480, 854))
        self.assertAlmostEqual(secs, 1.0, delta=0.3)


if __name__ == "__main__":
    unittest.main()
