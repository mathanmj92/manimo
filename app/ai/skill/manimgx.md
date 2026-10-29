# Engine: ManimGX

ManimGX runs Manim Community Edition's Python API on a GPU renderer. A scene file looks like this:

```python
import manimgx as m


class Name(m.Scene):
    def construct(self) -> None:
        ...
```

Rules specific to ManimGX:
- The first line is `import manimgx as m` (add `import numpy as np` if you use numpy). **Every** ManimGX name is used with the `m.` prefix: `m.Circle`, `m.Create`, `m.UP`, `m.BLUE_C`, `m.DEGREES`, `m.PI`. Never write `from manim import *`.
- Scenes derive from `m.Scene`; 3D scenes from `m.ThreeDScene`; scenes with a movable camera from `m.MovingCameraScene`.
- The API mirrors Manim CE: `self.play(...)`, `self.wait(...)`, `self.add(...)`, `self.remove(...)`, `self.clear()`, `mobject.animate.shift(...)`, `m.always_redraw`, `m.ValueTracker`, `m.Axes`, `axes.plot(...)`, `axes.c2p(...)`, `m.VGroup`, `.arrange(...)`, `.next_to(...)`, `.to_edge(...)`, `m.TransformMatchingTex`.
- `m.MathTex` takes LaTeX-style input (`\frac`, `\sum`, `\int`, `\sqrt`, `\vec`, `\hbar`, `\Delta`, `\Rightarrow` all work) and needs no LaTeX installation. `m.Text` is for plain words; always give a `font_size`.
- Sections: `self.next_section("Name", notes="speaker notes")` starts a slide for presenting. Use one per beat.
- Narration: `self.say(...)` exists (see the style guide) but only add it when asked.
- Video shape: wide 16:9 is the default. For a tall reel (9:16) put `m.config.pixel_width, m.config.pixel_height = 1080, 1920` right after the imports, and for square `1080, 1080`. The frame then has its short side 8 units (a tall frame is 8 wide and about 14.2 high), so lay content out in that space. Manimo's "Video shape" setting follows this when it is on "Same as my code".
- Several scenes in one file are fine; each scene is rendered on its own.
- Rendering is fast; do not worry about run time, worry about clarity.

How your answer is checked: Manimo runs `manimgx inspect` on your code. It reports Python errors with the line, and layout problems (clipped content, overlapping text, lines or fills over text, tiny labels) with the line and moment. If it reports problems you will be asked to fix them: change only what is needed and return the whole file again.
