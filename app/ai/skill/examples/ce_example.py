"""Area of a circle from its rings: unroll each ring into a thin strip and they make a triangle.

One idea: a circle's area is half its circumference times its radius, because the rings unroll into a triangle.
"""

from manim import *

C_RING = BLUE_C
C_ACCENT = YELLOW


class CircleAreaRings(Scene):
    def construct(self):
        title = Text("Why is a circle's area pi r squared?", font_size=36).to_edge(UP, buff=0.35)
        self.play(FadeIn(title, shift=DOWN * 0.2))

        # ---- beat 1: a circle made of rings
        self.next_section("Rings")
        rings = VGroup(*[
            Annulus(inner_radius=r - 0.15, outer_radius=r, color=C_RING, fill_opacity=0.35, stroke_width=1)
            for r in [0.15 * k for k in range(1, 11)]
        ]).move_to(LEFT * 3.2)
        self.play(LaggedStart(*[Create(r) for r in rings], lag_ratio=0.12), run_time=2.5)
        self.wait(0.5)

        # ---- beat 2: unroll them into strips that form a triangle
        self.next_section("Unroll")
        strips = VGroup(*[
            Rectangle(width=2 * PI * (0.15 * k - 0.075), height=0.15, color=C_RING, fill_opacity=0.35, stroke_width=1)
            for k in range(1, 11)
        ]).arrange(DOWN, buff=0.0, aligned_edge=LEFT).move_to(RIGHT * 2.2)
        self.play(*[ReplacementTransform(rings[k].copy(), strips[k]) for k in range(10)], run_time=3)
        self.wait(1)

        # ---- beat 3: read off the area
        self.next_section("Area")
        formula = Text("A = \u00bd \u00b7 (2\u03c0r) \u00b7 r = \u03c0r\u00b2", font_size=44, color=C_ACCENT).to_edge(DOWN, buff=0.5)   # Text, so no LaTeX is needed
        self.play(Write(formula))
        self.wait(1.5)
