"""Angles in a circle: the inscribed angle theorem and an isosceles triangle, solved step by step.

Problem: A, B, C lie on a circle with centre O and the central angle AOB is 100 degrees. Find x = angle ACB and y = angle OAB.

One idea: an inscribed angle is half the central angle on the same arc, and two radii make an isosceles triangle.
Beats: 1) problem  2) inscribed angle  3) isosceles triangle  4) drag C: x never changes.
"""

import math

import numpy as np

import manimgx as m

# ---- data, copied exactly from the problem
CENTRAL_DEG = 100.0

# ---- solution, computed once so the animation can never disagree with the answer
X_DEG = CENTRAL_DEG / 2                    # inscribed angle theorem
Y_DEG = (180.0 - CENTRAL_DEG) / 2          # base angles of the isosceles triangle OAB

# ---- colours: the same colour always means the same quantity
C_KNOWN = m.BLUE_C
C_UNKNOWN = m.YELLOW
C_FOUND = m.GREEN_C
C_AUX = m.TEAL
C_GUIDE = m.GREY_B

# ---- geometry (screen units)
CENTRE = np.array([-3.0, -0.3, 0.0])
RADIUS = 2.2
A_DEG = 270.0 - CENTRAL_DEG / 2     # A and B sit symmetrically below the centre
B_DEG = 270.0 + CENTRAL_DEG / 2


def on_circle(deg: float) -> np.ndarray:
    """The point of the circle at an angle `deg` (degrees, counter-clockwise from the right)."""
    return CENTRE + RADIUS * np.array([math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0.0])


def angle_arc(vertex: np.ndarray, p: np.ndarray, q: np.ndarray, radius: float, color) -> m.Arc:
    """The arc that marks the (smaller) angle between the rays vertex->p and vertex->q."""
    a1 = math.atan2(p[1] - vertex[1], p[0] - vertex[0])
    a2 = math.atan2(q[1] - vertex[1], q[0] - vertex[0])
    delta = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    return m.Arc(radius=radius, start_angle=a1, angle=delta, arc_center=vertex, color=color, stroke_width=4)


def angle_label_point(vertex: np.ndarray, p: np.ndarray, q: np.ndarray, distance: float) -> np.ndarray:
    """A point on the bisector of the angle, `distance` from the vertex (for the label)."""
    u = (p - vertex) / np.linalg.norm(p - vertex) + (q - vertex) / np.linalg.norm(q - vertex)
    return vertex + distance * u / np.linalg.norm(u)


class CircleAngles(m.Scene):
    def construct(self) -> None:
        title = m.Text("Angles in a circle", font_size=38).to_edge(m.UP, buff=0.35)
        self.play(m.FadeIn(title, shift=m.DOWN * 0.2))

        # ---- beat 1: the problem, redrawn from the data
        self.next_section("Problem", notes="Name the points. Ask: which angle is easier, the one at the centre or the one on the circle?")
        circle = m.Circle(radius=RADIUS, color=C_KNOWN, stroke_width=4).move_to(CENTRE)
        o_dot = m.Dot(CENTRE, radius=0.07, color=m.WHITE)
        a_pt, b_pt = on_circle(A_DEG), on_circle(B_DEG)
        c_deg = m.ValueTracker(90.0)
        c_pt = lambda: on_circle(c_deg.get_value())
        radius_a = m.Line(CENTRE, a_pt, color=C_AUX, stroke_width=4)
        radius_b = m.Line(CENTRE, b_pt, color=C_AUX, stroke_width=4)
        chord = m.Line(a_pt, b_pt, color=C_GUIDE, stroke_width=4)
        a_label = m.MathTex("A", font_size=36).move_to(a_pt + (a_pt - CENTRE) * 0.14)
        b_label = m.MathTex("B", font_size=36).move_to(b_pt + (b_pt - CENTRE) * 0.14)
        o_label = m.MathTex("O", font_size=36).next_to(o_dot, m.UP, buff=0.12)
        self.play(m.Create(circle), m.FadeIn(o_dot), m.Write(o_label))
        self.play(m.Create(radius_a), m.Create(radius_b), m.Create(chord), m.Write(a_label), m.Write(b_label))
        central = angle_arc(CENTRE, a_pt, b_pt, 0.6, C_KNOWN)
        central_label = m.MathTex(rf"{CENTRAL_DEG:g}^\circ", font_size=32, color=C_KNOWN).move_to(angle_label_point(CENTRE, a_pt, b_pt, 1.15))
        self.play(m.Create(central), m.Write(central_label))
        c_dot = m.always_redraw(lambda: m.Dot(c_pt(), radius=0.07, color=m.WHITE))
        c_label = m.always_redraw(lambda: m.MathTex("C", font_size=36).move_to(c_pt() + (c_pt() - CENTRE) * 0.14))
        line_ca = m.always_redraw(lambda: m.Line(c_pt(), a_pt, color=C_GUIDE, stroke_width=4))
        line_cb = m.always_redraw(lambda: m.Line(c_pt(), b_pt, color=C_GUIDE, stroke_width=4))
        self.play(m.FadeIn(c_dot), m.Write(c_label), m.Create(line_ca), m.Create(line_cb))
        find = m.MathTex(r"\text{Find }x=\angle ACB,\ y=\angle OAB", font_size=32, color=C_UNKNOWN)
        find.to_corner(m.UR, buff=0.5).shift(m.DOWN * 0.8)
        self.play(m.Write(find))
        self.wait(1.5)

        # ---- beat 2: the inscribed angle theorem
        self.next_section("Inscribed angle", notes="Theorem: an inscribed angle is half of the central angle that stands on the same arc.")
        x_arc = m.always_redraw(lambda: angle_arc(c_pt(), a_pt, b_pt, 0.55, C_UNKNOWN))
        x_label = m.always_redraw(lambda: m.MathTex("x", font_size=34, color=C_UNKNOWN).move_to(angle_label_point(c_pt(), a_pt, b_pt, 1.0)))
        self.play(m.Create(x_arc), m.Write(x_label))
        fact_1 = m.Text("Inscribed = half of central", font_size=28, color=C_AUX).move_to(m.RIGHT * 3.4 + m.UP * 1.9)
        self.play(m.Write(fact_1))
        self.play(m.Indicate(central), m.Indicate(x_arc))
        eq_x = m.MathTex(rf"x=\tfrac12\,({CENTRAL_DEG:g}^\circ)={X_DEG:g}^\circ", font_size=36, color=C_FOUND)
        eq_x.next_to(fact_1, m.DOWN, buff=0.4, aligned_edge=m.LEFT)
        self.play(m.TransformFromCopy(central_label, eq_x))
        self.wait(2)

        # ---- beat 3: the isosceles triangle OAB
        self.next_section("Isosceles triangle", notes="OA and OB are radii, so equal. The base angles of the isosceles triangle are equal too.")
        self.play(m.FadeOut(x_arc), m.FadeOut(x_label), m.FadeOut(line_ca), m.FadeOut(line_cb), m.FadeOut(c_dot), m.FadeOut(c_label))
        tri = m.Polygon(CENTRE, a_pt, b_pt, color=C_AUX, fill_color=C_AUX, fill_opacity=0.2, stroke_width=0)
        self.play(m.FadeIn(tri))
        fact_2 = m.Text("OA = OB (radii), so the base angles match", font_size=26, color=C_AUX)
        fact_2.scale_to_fit_width(5.2).next_to(eq_x, m.DOWN, buff=0.5, aligned_edge=m.LEFT)
        self.play(m.Write(fact_2))
        y_arc = angle_arc(a_pt, CENTRE, b_pt, 0.55, C_UNKNOWN)
        y_label = m.MathTex("y", font_size=34, color=C_UNKNOWN).move_to(angle_label_point(a_pt, CENTRE, b_pt, 1.0))
        y_arc_b = angle_arc(b_pt, CENTRE, a_pt, 0.55, C_UNKNOWN)
        self.play(m.Create(y_arc), m.Create(y_arc_b), m.Write(y_label))
        eq_y = m.MathTex(rf"y=\frac{{180^\circ-{CENTRAL_DEG:g}^\circ}}{{2}}={Y_DEG:g}^\circ", font_size=36, color=C_FOUND)
        eq_y.next_to(fact_2, m.DOWN, buff=0.4, aligned_edge=m.LEFT)
        self.play(m.Write(eq_y))
        self.play(m.Create(m.SurroundingRectangle(m.VGroup(eq_x), color=m.GREEN, buff=0.12)),
                  m.Create(m.SurroundingRectangle(m.VGroup(eq_y), color=m.GREEN, buff=0.12)))
        self.wait(2)

        # ---- beat 4: drag C along the circle, x does not change
        self.next_section("Drag C", notes="Move C anywhere on the big arc: the angle x stays the same. That is why the theorem is useful.")
        self.play(m.FadeOut(tri), m.FadeOut(y_arc), m.FadeOut(y_arc_b), m.FadeOut(y_label))
        x_arc_2 = m.always_redraw(lambda: angle_arc(c_pt(), a_pt, b_pt, 0.55, C_UNKNOWN))
        x_label_2 = m.always_redraw(lambda: m.MathTex(rf"{X_DEG:g}^\circ", font_size=32, color=C_UNKNOWN).move_to(
            angle_label_point(c_pt(), a_pt, b_pt, 1.0)))
        c_dot_2 = m.always_redraw(lambda: m.Dot(c_pt(), radius=0.07, color=m.WHITE))
        c_label_2 = m.always_redraw(lambda: m.MathTex("C", font_size=36).move_to(c_pt() + (c_pt() - CENTRE) * 0.14))
        line_ca_2 = m.always_redraw(lambda: m.Line(c_pt(), a_pt, color=C_GUIDE, stroke_width=4))
        line_cb_2 = m.always_redraw(lambda: m.Line(c_pt(), b_pt, color=C_GUIDE, stroke_width=4))
        self.add(c_dot_2, c_label_2, line_ca_2, line_cb_2, x_arc_2, x_label_2)
        self.play(c_deg.animate.set_value(150.0), run_time=2.5)
        self.play(c_deg.animate.set_value(30.0), run_time=3.5)
        self.play(c_deg.animate.set_value(90.0), run_time=2)
        self.wait(1.5)
