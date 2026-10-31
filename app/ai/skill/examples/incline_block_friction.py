"""Block sliding down a rough incline: free-body diagram, then the acceleration step by step.

Problem: a 10 kg block slides down a 30 degree incline, kinetic friction coefficient 0.2, g = 9.81 m/s^2.
Find the normal force, the friction force and the acceleration.

One idea: choose axes along the slope; the forces perpendicular to the slope cancel, the ones along it decide the acceleration.
Beats: 1) problem  2) free-body diagram  3) axes and components  4) perpendicular equation  5) parallel equation  6) answer and motion.
"""

import math

import numpy as np

import manimgx as m

# ---- data, copied exactly from the problem
MASS = 10.0          # kg
THETA_DEG = 30.0     # degrees
MU = 0.2             # kinetic friction coefficient
G = 9.81             # m/s^2

# ---- solution, computed once so the animation can never disagree with the answer
THETA = math.radians(THETA_DEG)
WEIGHT = MASS * G
NORMAL = WEIGHT * math.cos(THETA)
FRICTION = MU * NORMAL
ALONG = WEIGHT * math.sin(THETA)
ACCEL = (ALONG - FRICTION) / MASS      # = g (sin - mu cos)

# ---- colours: the same colour always means the same quantity
C_BODY = m.BLUE_C
C_SURFACE = m.GREY_B
C_WEIGHT = m.RED_C
C_NORMAL = m.GREEN_C
C_FRICTION = m.ORANGE
C_ACCEL = m.PURPLE_B
C_RESULT = m.GREEN
C_AXIS = m.GREY_C

# ---- geometry (screen units) and force scale
FORCE_SCALE = 0.02    # 1 N = 0.02 screen units, so mg = 98.1 N is about 1.96 long
P_BOTTOM = np.array([-0.2, -2.6, 0.0])                       # bottom end of the slope (angle theta)
P_TOP = P_BOTTOM + np.array([-5.0, 5.0 * math.tan(THETA), 0.0])
P_CORNER = np.array([P_TOP[0], P_BOTTOM[1], 0.0])
DOWN_SLOPE = np.array([math.cos(THETA), -math.sin(THETA), 0.0])
UP_SLOPE = -DOWN_SLOPE
OUT_NORMAL = np.array([math.sin(THETA), math.cos(THETA), 0.0])
BLOCK_SIDE = 0.8
BLOCK_START_S = 2.4                                          # distance of the block from the top, along the slope


def block_centre(s: float) -> np.ndarray:
    """Centre of the block when it has gone a distance s along the slope from its start."""
    return P_TOP + DOWN_SLOPE * (BLOCK_START_S + s) + OUT_NORMAL * BLOCK_SIDE / 2


def force_arrow(origin: np.ndarray, direction: np.ndarray, newtons: float, color) -> m.Arrow:
    """An arrow whose length is proportional to the force."""
    end = origin + direction * newtons * FORCE_SCALE
    return m.Arrow(origin, end, buff=0, color=color, stroke_width=6, tip_length=0.2)


class InclineBlockFriction(m.Scene):
    def construct(self) -> None:
        title = m.Text("Block on a rough incline", font_size=38).to_edge(m.UP, buff=0.35)
        self.play(m.FadeIn(title, shift=m.DOWN * 0.2))

        # ---- beat 1: the problem, redrawn cleanly
        self.next_section("Problem", notes="Read the problem. Ask: which way will it accelerate, and why is it less than g sin(theta)?")
        slope = m.Polygon(P_TOP, P_BOTTOM, P_CORNER, color=C_SURFACE, fill_color=C_SURFACE, fill_opacity=0.15, stroke_width=4)
        block = m.Square(side_length=BLOCK_SIDE, color=C_BODY, fill_color=C_BODY, fill_opacity=0.35, stroke_width=4)
        block.rotate(-THETA).move_to(block_centre(0.0))
        arc = m.Arc(radius=0.7, start_angle=math.pi - THETA, angle=THETA, arc_center=P_BOTTOM, color=C_AXIS, stroke_width=3)
        theta_label = m.MathTex(r"30^\circ", font_size=30, color=C_AXIS).move_to(
            P_BOTTOM + 1.15 * np.array([math.cos(math.pi - THETA / 2), math.sin(math.pi - THETA / 2), 0.0]))
        given = m.MathTex(r"m=10\,\mathrm{kg},\ \mu=0.2,\ g=9.81\,\mathrm{m/s^2}", font_size=30, color=m.GREY_B)
        given.to_edge(m.DOWN, buff=0.4).to_edge(m.LEFT, buff=0.6)
        self.play(m.Create(slope), m.FadeIn(block))
        self.play(m.Create(arc), m.Write(theta_label), m.FadeIn(given))
        find = m.Text("Find: N, f, a", font_size=32, color=m.YELLOW).to_corner(m.UR, buff=0.5).shift(m.DOWN * 0.8)
        self.play(m.Write(find))
        self.wait(1.5)

        # ---- beat 2: free-body diagram, one force at a time (weight, normal, friction)
        self.next_section("Free-body diagram", notes="Draw every force on the block. Weight, normal, friction up the slope because it slides down.")
        centre = block_centre(0.0)
        weight = force_arrow(centre, m.DOWN, WEIGHT, C_WEIGHT)
        normal = force_arrow(centre, OUT_NORMAL, NORMAL, C_NORMAL)
        friction = force_arrow(centre, UP_SLOPE, FRICTION, C_FRICTION)
        w_label = m.MathTex(r"mg", font_size=34, color=C_WEIGHT).next_to(weight.get_end(), m.DOWN, buff=0.12)
        n_label = m.MathTex(r"N", font_size=34, color=C_NORMAL).next_to(normal.get_end(), m.UP, buff=0.12)
        f_label = m.MathTex(r"f", font_size=34, color=C_FRICTION).next_to(friction.get_end(), m.UL, buff=0.08)
        for arrow, label in [(weight, w_label), (normal, n_label), (friction, f_label)]:
            self.play(m.GrowArrow(arrow))
            self.play(m.Write(label), run_time=0.6)
            self.wait(0.4)
        self.wait(1)

        # ---- beat 3: axes along the slope and the components of the weight
        self.next_section("Axes and components", notes="Choose x along the slope: then only the weight has to be split.")
        ax_origin = P_TOP + np.array([0.3, 1.2, 0.0])   # empty space above the slope
        axis_x = m.Arrow(ax_origin, ax_origin + DOWN_SLOPE * 0.9, buff=0, color=C_AXIS, stroke_width=3, tip_length=0.15)
        axis_y = m.Arrow(ax_origin, ax_origin + OUT_NORMAL * 0.9, buff=0, color=C_AXIS, stroke_width=3, tip_length=0.15)
        x_label = m.MathTex(r"x", font_size=36, color=C_AXIS).next_to(axis_x.get_end(), m.RIGHT, buff=0.08)
        y_label = m.MathTex(r"y", font_size=36, color=C_AXIS).next_to(axis_y.get_end(), m.UP, buff=0.08)
        self.play(m.GrowArrow(axis_x), m.GrowArrow(axis_y), m.Write(x_label), m.Write(y_label))
        along = force_arrow(centre, DOWN_SLOPE, ALONG, C_WEIGHT)
        into = force_arrow(centre, -OUT_NORMAL, WEIGHT * math.cos(THETA), C_WEIGHT)
        for part in (along, into):
            part.set_opacity(0.55).set_stroke(width=4)
        along_label = m.MathTex(r"mg\sin\theta", font_size=30, color=C_WEIGHT).next_to(along.get_end(), m.RIGHT, buff=0.1)
        into_label = m.MathTex(r"mg\cos\theta", font_size=30, color=C_WEIGHT).next_to(into.get_end(), m.DOWN, buff=0.1).shift(m.LEFT * 0.7)
        self.play(m.TransformFromCopy(weight, along), m.TransformFromCopy(weight, into), run_time=1.5)
        self.play(m.Write(along_label), m.Write(into_label))
        self.wait(1.5)

        # ---- beat 4: perpendicular to the slope, nothing accelerates that way
        self.next_section("Perpendicular", notes="No acceleration perpendicular to the slope, so the forces there balance.")
        eq_perp = m.MathTex("N", r"-mg\cos\theta=0", font_size=34).move_to(m.RIGHT * 3.3 + m.UP * 1.9)
        eq_perp[0].set_color(C_NORMAL)
        self.play(m.TransformFromCopy(normal, eq_perp), run_time=1.5)
        self.wait(0.5)
        eq_n = m.MathTex(rf"N={MASS:g}({G:g})\cos 30^\circ={NORMAL:.1f}\ \mathrm{{N}}", font_size=34, color=C_NORMAL)
        eq_n.next_to(eq_perp, m.DOWN, buff=0.4, aligned_edge=m.LEFT)
        self.play(m.Write(eq_n))
        eq_f = m.MathTex(rf"f=\mu N={MU:g}({NORMAL:.1f})={FRICTION:.1f}\ \mathrm{{N}}", font_size=34, color=C_FRICTION)
        eq_f.next_to(eq_n, m.DOWN, buff=0.4, aligned_edge=m.LEFT)
        self.play(m.Write(eq_f))
        self.wait(2)

        # ---- beat 5: along the slope, Newton's second law
        self.next_section("Along the slope", notes="Net force along the slope equals mass times acceleration. Watch the sign of friction.")
        self.play(m.FadeOut(eq_perp), m.FadeOut(eq_n), m.FadeOut(eq_f))
        eq_law = m.MathTex(r"mg\sin\theta", "-", "f", "=", "ma", font_size=34).move_to(m.RIGHT * 3.3 + m.UP * 1.9)
        eq_law[0].set_color(C_WEIGHT)
        eq_law[2].set_color(C_FRICTION)
        self.play(m.TransformFromCopy(along, eq_law[0]), m.TransformFromCopy(friction, eq_law[2]), m.Write(eq_law[1]),
                  m.Write(eq_law[3]), m.Write(eq_law[4]), run_time=2)
        self.wait(0.5)
        eq_sub = m.MathTex(rf"{ALONG:.1f}-{FRICTION:.1f}={MASS:g}\,a", font_size=34)
        eq_sub.next_to(eq_law, m.DOWN, buff=0.4, aligned_edge=m.LEFT)
        self.play(m.Write(eq_sub))
        self.wait(0.5)
        eq_a = m.MathTex(rf"a={ACCEL:.2f}\ \mathrm{{m/s^2}}", font_size=38, color=C_RESULT)
        eq_a.next_to(eq_sub, m.DOWN, buff=0.4, aligned_edge=m.LEFT)
        self.play(m.Write(eq_a))
        box = m.SurroundingRectangle(eq_a, color=C_RESULT, buff=0.12)
        self.play(m.Create(box))
        self.wait(1.5)

        # ---- beat 6: the motion that the answer predicts
        self.next_section("Motion", notes="Let it slide: constant acceleration. Ask what changes if friction is larger.")
        self.play(*[m.FadeOut(mob) for mob in (weight, normal, friction, w_label, n_label, f_label, along, into, along_label, into_label,
                                              axis_x, axis_y, x_label, y_label)])
        t = m.ValueTracker(0.0)
        block.add_updater(lambda mob: mob.move_to(block_centre(0.5 * ACCEL * t.get_value() ** 2)))
        accel_arrow = m.always_redraw(
            lambda: m.Arrow(block.get_center(), block.get_center() + DOWN_SLOPE * 0.9, buff=0, color=C_ACCEL, stroke_width=5, tip_length=0.18))
        accel_label = m.always_redraw(lambda: m.MathTex(r"a", font_size=34, color=C_ACCEL).next_to(accel_arrow.get_end(), m.DOWN, buff=0.12))
        self.add(accel_arrow, accel_label)
        self.play(t.animate.set_value(1.1), run_time=2.5, rate_func=m.linear)
        block.clear_updaters()
        self.wait(1.5)
