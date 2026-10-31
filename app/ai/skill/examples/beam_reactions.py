"""Support reactions of a simply supported beam with one point load, solved with moments and forces.

Problem: a 6 m beam is pinned at A and on a roller at B. A 12 kN load acts 2 m from A. Find the reactions R_A and R_B.

One idea: take moments about the point that removes an unknown, then use the force balance for the rest.
Beats: 1) problem  2) free-body diagram  3) moments about A  4) forces in y  5) check about B.
"""

import numpy as np

import manimgx as m

# ---- data, copied exactly from the problem
SPAN = 6.0     # m
LOAD = 12.0    # kN
LOAD_X = 2.0   # m from A

# ---- solution, computed once so the animation can never disagree with the answer
R_B = LOAD * LOAD_X / SPAN        # sum of moments about A = 0
R_A = LOAD - R_B                  # sum of forces in y = 0
CHECK_B = R_A * SPAN - LOAD * (SPAN - LOAD_X)   # moments about B must be 0

# ---- colours: the same colour always means the same quantity
C_BEAM = m.BLUE_C
C_LOAD = m.YELLOW
C_REACT = m.GREEN_C
C_GUIDE = m.GREY_B
C_RESULT = m.GREEN

# ---- geometry: 1 m = 0.9 units along the beam, 1 kN = 0.2 units for arrows
M_TO_UNITS = 0.9
KN_TO_UNITS = 0.2
BEAM_Y = 1.0
X_A = -6.0


def x_of(distance: float) -> float:
    """Screen x of a point `distance` metres from A."""
    return X_A + distance * M_TO_UNITS


def up_arrow(x: float, kn: float, color) -> m.Arrow:
    """A reaction arrow below the support, its tip touching the support's base."""
    tip_y = BEAM_Y - 0.5
    return m.Arrow(np.array([x, tip_y - kn * KN_TO_UNITS, 0.0]), np.array([x, tip_y, 0.0]), buff=0, color=color, stroke_width=6, tip_length=0.2)


class BeamReactions(m.Scene):
    def construct(self) -> None:
        title = m.Text("Reactions of a simply supported beam", font_size=36).to_edge(m.UP, buff=0.35)
        self.play(m.FadeIn(title, shift=m.DOWN * 0.2))

        # ---- beat 1: the problem
        self.next_section("Problem", notes="Two unknown reactions, so we need two equations. Ask which point makes one unknown disappear.")
        beam = m.Rectangle(width=SPAN * M_TO_UNITS, height=0.2, color=C_BEAM, fill_color=C_BEAM, fill_opacity=0.4, stroke_width=4)
        beam.move_to(np.array([x_of(SPAN / 2), BEAM_Y, 0.0]))
        pin = m.Triangle(color=C_GUIDE, fill_color=C_GUIDE, fill_opacity=0.3, stroke_width=3).scale(0.28)
        pin.next_to(np.array([x_of(0), BEAM_Y - 0.1, 0.0]), m.DOWN, buff=0)
        roller = m.Triangle(color=C_GUIDE, fill_color=C_GUIDE, fill_opacity=0.3, stroke_width=3).scale(0.28)
        roller.next_to(np.array([x_of(SPAN), BEAM_Y - 0.1, 0.0]), m.DOWN, buff=0)
        wheel = m.Circle(radius=0.1, color=C_GUIDE, stroke_width=3).next_to(roller, m.DOWN, buff=0)
        pin_label = m.MathTex("A", font_size=36).next_to(beam.get_left(), m.UP, buff=0.3)
        roller_label = m.MathTex("B", font_size=36).next_to(beam.get_right(), m.UP, buff=0.3)
        load = m.Arrow(np.array([x_of(LOAD_X), BEAM_Y + 1.5, 0.0]), np.array([x_of(LOAD_X), BEAM_Y + 0.1, 0.0]), buff=0, color=C_LOAD,
                       stroke_width=6, tip_length=0.2)
        load_label = m.MathTex(rf"{LOAD:g}\ \mathrm{{kN}}", font_size=34, color=C_LOAD).next_to(load, m.UP, buff=0.12)
        self.play(m.Create(beam), m.Create(pin), m.Create(roller), m.Create(wheel))
        self.play(m.Write(pin_label), m.Write(roller_label))
        self.play(m.GrowArrow(load), m.Write(load_label))
        dim_y = -2.3
        dim_a = m.DoubleArrow(np.array([x_of(0), dim_y, 0.0]), np.array([x_of(LOAD_X), dim_y, 0.0]), buff=0, color=C_GUIDE, stroke_width=3, tip_length=0.15)
        dim_b = m.DoubleArrow(np.array([x_of(LOAD_X), dim_y, 0.0]), np.array([x_of(SPAN), dim_y, 0.0]), buff=0, color=C_GUIDE, stroke_width=3, tip_length=0.15)
        dim_a_label = m.MathTex(rf"{LOAD_X:g}\ \mathrm{{m}}", font_size=30, color=C_GUIDE).next_to(dim_a, m.DOWN, buff=0.12)
        dim_b_label = m.MathTex(rf"{SPAN - LOAD_X:g}\ \mathrm{{m}}", font_size=30, color=C_GUIDE).next_to(dim_b, m.DOWN, buff=0.12)
        self.play(m.Create(dim_a), m.Create(dim_b), m.Write(dim_a_label), m.Write(dim_b_label))
        find = m.Text("Find: R_A, R_B", font_size=32, color=m.YELLOW).to_corner(m.UR, buff=0.5).shift(m.DOWN * 0.8)
        self.play(m.Write(find))
        self.wait(1.5)

        # ---- beat 2: free-body diagram (reactions at the supports)
        self.next_section("Free-body diagram", notes="Pin: any direction, but with only vertical load its reaction is vertical. Roller: vertical only.")
        arrow_a = up_arrow(x_of(0), 8.0, C_REACT)        # unknown size, so start with equal arrows; they are resized when each reaction is found
        arrow_b = up_arrow(x_of(SPAN), 8.0, C_REACT)
        label_a = m.MathTex("R_A", font_size=34, color=C_REACT).next_to(arrow_a, m.RIGHT, buff=0.12)
        label_b = m.MathTex("R_B", font_size=34, color=C_REACT).next_to(arrow_b, m.LEFT, buff=0.12)
        self.play(m.GrowArrow(arrow_a), m.GrowArrow(arrow_b))
        self.play(m.Write(label_a), m.Write(label_b))
        self.wait(1.5)

        # ---- beat 3: moments about A
        self.next_section("Moments about A", notes="Taking moments about A removes R_A, because its lever arm is zero.")
        flash = m.Flash(pin, color=m.YELLOW, flash_radius=0.4)
        self.play(flash)
        eq1 = m.MathTex(r"\sum M_A=0:\ R_B(6)-12(2)=0", font_size=34).move_to(m.RIGHT * 3.4 + m.UP * 1.9)
        self.play(m.Write(eq1))
        self.wait(0.5)
        eq2 = m.MathTex(rf"R_B=\frac{{{LOAD:g}\cdot{LOAD_X:g}}}{{{SPAN:g}}}={R_B:g}\ \mathrm{{kN}}", font_size=36, color=C_REACT)
        eq2.next_to(eq1, m.DOWN, buff=0.45, aligned_edge=m.LEFT)
        self.play(m.Write(eq2))
        new_b = up_arrow(x_of(SPAN), R_B, C_REACT)
        self.play(m.Transform(arrow_b, new_b), label_b.animate.next_to(new_b, m.LEFT, buff=0.12))
        self.wait(1.5)

        # ---- beat 4: forces in y
        self.next_section("Forces in y", notes="Everything upward equals everything downward.")
        eq3 = m.MathTex(r"\sum F_y=0:\ R_A+R_B-12=0", font_size=34).next_to(eq2, m.DOWN, buff=0.45, aligned_edge=m.LEFT)
        self.play(m.Write(eq3))
        eq4 = m.MathTex(rf"R_A={LOAD:g}-{R_B:g}={R_A:g}\ \mathrm{{kN}}", font_size=36, color=C_REACT)
        eq4.next_to(eq3, m.DOWN, buff=0.45, aligned_edge=m.LEFT)
        self.play(m.Write(eq4))
        new_a = up_arrow(x_of(0), R_A, C_REACT)
        self.play(m.Transform(arrow_a, new_a), label_a.animate.next_to(new_a, m.RIGHT, buff=0.12))
        self.play(m.Create(m.SurroundingRectangle(eq2, color=C_RESULT, buff=0.12)), m.Create(m.SurroundingRectangle(eq4, color=C_RESULT, buff=0.12)))
        self.wait(1.5)

        # ---- beat 5: check with moments about B
        self.next_section("Check", notes="A good habit: moments about the other support must also be zero.")
        check = m.MathTex(rf"\sum M_B:\ {R_A:g}(6)-12(4)={CHECK_B:g}\ \checkmark", font_size=32, color=m.GREY_B)
        check.to_edge(m.DOWN, buff=0.4).to_edge(m.RIGHT, buff=0.5)
        self.play(m.Write(check))
        self.wait(2)
