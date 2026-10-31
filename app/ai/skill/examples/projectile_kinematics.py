"""Projectile motion: split the launch velocity, then find the maximum height, the flight time and the range.

Problem: a ball is launched from the ground at 20 m/s, 40 degrees above the horizontal (g = 9.81 m/s^2, no air resistance).
Find the maximum height H, the time of flight T and the range R.

One idea: horizontal and vertical motion are independent; at the top the vertical velocity is zero.
Beats: 1) problem  2) components  3) top of the flight  4) time and range  5) check with the trajectory.
"""

import math

import numpy as np

import manimgx as m

# ---- data, copied exactly from the problem
SPEED = 20.0        # m/s
ANGLE_DEG = 40.0    # degrees
G = 9.81            # m/s^2

# ---- solution, computed once so the animation can never disagree with the answer
ANGLE = math.radians(ANGLE_DEG)
VX = SPEED * math.cos(ANGLE)
VY0 = SPEED * math.sin(ANGLE)
T_UP = VY0 / G                      # vy = vy0 - g t = 0
HEIGHT = VY0 ** 2 / (2 * G)
T_FLIGHT = 2 * T_UP
RANGE = VX * T_FLIGHT

# ---- colours: the same colour always means the same quantity
C_VEL = m.TEAL_C
C_ACCEL = m.PURPLE_B
C_PATH = m.BLUE_C
C_GUIDE = m.GREY_B
C_RESULT = m.GREEN
C_ASK = m.YELLOW

VEL_SCALE = 0.075   # 1 m/s = 0.075 screen units


def position(t: float) -> tuple[float, float]:
    """Horizontal and vertical position (m) at time t."""
    return VX * t, VY0 * t - 0.5 * G * t * t


class ProjectileKinematics(m.Scene):
    def construct(self) -> None:
        title = m.Text("Projectile motion", font_size=38).to_edge(m.UP, buff=0.35)
        self.play(m.FadeIn(title, shift=m.DOWN * 0.2))

        # ---- beat 1: the problem, with the ground and the launch
        self.next_section("Problem", notes="Ask: which is bigger, the height or the range? What is the vertical velocity at the top?")
        axes = m.Axes(x_range=[0, 45, 10], y_range=[0, 10, 5], x_length=7.0, y_length=3.0,
                      axis_config={"color": C_GUIDE, "include_ticks": False, "include_tip": False}).move_to(m.LEFT * 2.6 + m.DOWN * 0.7)
        ball = m.Dot(axes.c2p(0, 0), radius=0.12, color=m.WHITE)
        given = m.MathTex(r"v_0=20\,\mathrm{m/s},\ \theta=40^\circ,\ g=9.81\,\mathrm{m/s^2}", font_size=30, color=C_GUIDE)
        given.to_edge(m.DOWN, buff=0.4).to_edge(m.LEFT, buff=0.6)
        find = m.Text("Find: H, T, R", font_size=32, color=C_ASK).to_corner(m.UR, buff=0.5).shift(m.DOWN * 0.8)
        self.play(m.Create(axes), m.FadeIn(ball))
        self.play(m.FadeIn(given), m.Write(find))
        self.wait(1.5)

        # ---- beat 2: split the velocity into components
        self.next_section("Components", notes="The launch velocity is the diagonal of a rectangle: horizontal and vertical parts.")
        origin = axes.c2p(0, 0)
        v0 = m.Arrow(origin, origin + np.array([VX, VY0, 0.0]) * VEL_SCALE * 1.0, buff=0, color=C_VEL, stroke_width=6, tip_length=0.2)
        v0_label = m.MathTex(r"v_0", font_size=34, color=C_VEL).next_to(v0.get_end(), m.UL, buff=0.08)
        self.play(m.GrowArrow(v0), m.Write(v0_label))
        vx_arrow = m.Arrow(origin, origin + np.array([VX * VEL_SCALE, 0.0, 0.0]), buff=0, color=C_VEL, stroke_width=4, tip_length=0.15)
        vy_arrow = m.Arrow(origin, origin + np.array([0.0, VY0 * VEL_SCALE, 0.0]), buff=0, color=C_VEL, stroke_width=4, tip_length=0.15)
        vx_label = m.MathTex(r"v_x", font_size=30, color=C_VEL).next_to(vx_arrow, m.DOWN, buff=0.1)
        vy_label = m.MathTex(r"v_{y0}", font_size=30, color=C_VEL).next_to(vy_arrow, m.LEFT, buff=0.1)
        self.play(m.TransformFromCopy(v0, vx_arrow), m.TransformFromCopy(v0, vy_arrow), run_time=1.5)
        self.play(m.Write(vx_label), m.Write(vy_label))
        eq_x = m.MathTex(rf"v_x=20\cos 40^\circ={VX:.1f}\ \mathrm{{m/s}}", font_size=32, color=C_VEL).move_to(m.RIGHT * 3.4 + m.UP * 1.9)
        eq_y = m.MathTex(rf"v_{{y0}}=20\sin 40^\circ={VY0:.1f}\ \mathrm{{m/s}}", font_size=32, color=C_VEL)
        eq_y.next_to(eq_x, m.DOWN, buff=0.35, aligned_edge=m.LEFT)
        self.play(m.Write(eq_x))
        self.play(m.Write(eq_y))
        self.wait(2)

        # ---- beat 3: top of the flight, the vertical velocity is zero
        self.next_section("Top of the flight", notes="At the top the ball only moves sideways. Use v_y = 0 to find the time and the height.")
        self.play(m.FadeOut(v0), m.FadeOut(v0_label), m.FadeOut(vx_arrow), m.FadeOut(vy_arrow), m.FadeOut(vx_label), m.FadeOut(vy_label),
                  m.FadeOut(eq_x), m.FadeOut(eq_y))
        path = m.ParametricFunction(lambda t: axes.c2p(*position(t)), t_range=[0, T_UP], color=C_PATH, stroke_width=5)
        self.play(m.MoveAlongPath(ball, path), m.Create(path), run_time=2.5, rate_func=m.linear)
        apex_x, apex_y = position(T_UP)
        top_line = m.DashedLine(axes.c2p(apex_x, 0), axes.c2p(apex_x, apex_y), color=C_GUIDE, stroke_width=3)
        h_label = m.MathTex("H", font_size=34, color=C_RESULT).next_to(top_line, m.RIGHT, buff=0.12)
        v_top = m.Arrow(ball.get_center(), ball.get_center() + m.RIGHT * VX * VEL_SCALE, buff=0, color=C_VEL, stroke_width=5, tip_length=0.18)
        self.play(m.Create(top_line), m.GrowArrow(v_top), m.Write(h_label))
        eq_t = m.MathTex(rf"v_y=v_{{y0}}-gt=0\ \Rightarrow\ t={T_UP:.2f}\ \mathrm{{s}}", font_size=30).move_to(m.RIGHT * 3.4 + m.UP * 1.9)
        eq_h = m.MathTex(rf"H=\frac{{v_{{y0}}^2}}{{2g}}={HEIGHT:.2f}\ \mathrm{{m}}", font_size=34, color=C_RESULT)
        eq_h.next_to(eq_t, m.DOWN, buff=0.4, aligned_edge=m.LEFT)
        self.play(m.Write(eq_t))
        self.play(m.Write(eq_h))
        self.wait(2)

        # ---- beat 4: the way down is the mirror image, so T = 2t and R = vx T
        self.next_section("Time and range", notes="Up and down take the same time. Horizontal speed never changes, so range is v_x times T.")
        self.play(m.FadeOut(v_top), m.FadeOut(eq_t))
        path_down = m.ParametricFunction(lambda t: axes.c2p(*position(t)), t_range=[T_UP, T_FLIGHT], color=C_PATH, stroke_width=5)
        self.play(m.MoveAlongPath(ball, path_down), m.Create(path_down), run_time=2.5, rate_func=m.linear)
        range_arrow = m.DoubleArrow(axes.c2p(0, 0) + m.DOWN * 0.45, axes.c2p(RANGE, 0) + m.DOWN * 0.45, buff=0, color=C_RESULT, stroke_width=4, tip_length=0.15)
        r_label = m.MathTex("R", font_size=34, color=C_RESULT).next_to(range_arrow, m.DOWN, buff=0.1)
        self.play(m.Create(range_arrow), m.Write(r_label))
        eq_tt = m.MathTex(rf"T=2t={T_FLIGHT:.2f}\ \mathrm{{s}}", font_size=34, color=C_RESULT)
        eq_tt.next_to(eq_h, m.DOWN, buff=0.4, aligned_edge=m.LEFT)
        eq_r = m.MathTex(rf"R=v_xT={VX:.1f}({T_FLIGHT:.2f})={RANGE:.1f}\ \mathrm{{m}}", font_size=34, color=C_RESULT)
        eq_r.next_to(eq_tt, m.DOWN, buff=0.4, aligned_edge=m.LEFT)
        self.play(m.Write(eq_tt))
        self.play(m.Write(eq_r))
        self.play(m.Create(m.SurroundingRectangle(m.VGroup(eq_h, eq_tt, eq_r), color=C_RESULT, buff=0.15)))
        self.wait(2)

        # ---- beat 5: check with the range formula
        self.next_section("Check", notes="Optional: the range formula gives the same number. Which angle gives the longest range?")
        check = m.MathTex(rf"R=\frac{{v_0^2\sin 2\theta}}{{g}}={RANGE:.1f}\ \mathrm{{m}}\ \checkmark", font_size=32, color=C_GUIDE)
        check.to_edge(m.DOWN, buff=0.4).to_edge(m.RIGHT, buff=0.5)
        self.play(m.Write(check))
        self.wait(2)
