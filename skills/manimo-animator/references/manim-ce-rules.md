# Engine: Manim Community Edition

A scene file looks like this:

```python
from manim import *


class Name(Scene):
    def construct(self):
        ...
```

Rules specific to Manim CE:
- Start with `from manim import *` (plus `import numpy as np` if needed). Names are used without a prefix: `Circle`, `Create`, `UP`, `BLUE_C`.
- Scenes derive from `Scene`, `ThreeDScene` or `MovingCameraScene`.
- `MathTex` and `Tex` need LaTeX on the computer. If the user has no LaTeX, prefer `Text` and `DecimalNumber`, and say so briefly.
- Everything in the style guide applies, but use `Transform`, `ReplacementTransform`, `TransformMatchingTex`, `Write`, `Create`, `FadeIn`, `LaggedStart` and `AnimationGroup` from the Manim CE API.
- `self.next_section("Name")` exists in Manim CE too.
- Do not use plugins such as manim-voiceover, manim-slides or manim-physics.

How your answer is checked: Manimo compiles your code and renders it once at low quality to catch errors. If it fails you will get the error and line; fix only what is needed and return the whole file again.
