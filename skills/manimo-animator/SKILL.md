---
name: manimo-animator
description: Write explainer-quality math and science animations in ManimGX (import manimgx as m) or Manim Community Edition, in the style of 3Blue1Brown-type channels, then check them for errors and layout problems. Use when the user asks for an animation, a visual explanation, a Manim or ManimGX scene, or wants an existing scene fixed or improved.
---

# Manimo animator

You write complete, runnable Python files that teach one idea visually. The picture explains; words only name what is visible.

## Workflow
1. Decide the engine: code that starts with `import manimgx as m` is ManimGX; `from manim import *` is Manim Community Edition. If the user does not say, use ManimGX.
2. Read `references/style-guide.md` and the rules for the engine (`references/manimgx-rules.md` or `references/manim-ce-rules.md`). For ManimGX also keep `references/valid-names.md` open and use only names from it.
3. Look at the closest file in `examples/` for structure, pacing and layout before you write.
4. Write the full scene file: docstring with the one idea, palette constants, helpers, one scene class, one commented beat per `self.next_section(...)`.
5. **Check it.** For ManimGX run `manimgx inspect scene.py SceneName` (it prints errors with the line, and layout problems such as overlapping text or content outside the frame, and writes a storyboard PNG you can look at). Fix every problem, change only what is needed, and run it again until it prints "layout: no problems". For Manim CE render once with `manim render -ql scene.py SceneName`.
6. Reply with a 2 to 4 sentence plan, the file, and one to three short tweak suggestions.

## Safety
Animation code must not read or write files, use the network, run subprocesses or call `eval`/`exec`. Do not import anything except manimgx, manim, numpy, math, random and similar plain libraries.
