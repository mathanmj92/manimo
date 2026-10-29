"""The derivative as the slope of a tangent line that slides along a curve.

One idea: the derivative at x is how steep the curve is at x.
Beats: 1) the curve  2) a tangent line sliding along it, its slope shown live  3) the slope IS the derivative.
"""

import numpy as np

import manimgx as m

C_CURVE = m.BLUE_C
C_TANGENT = m.YELLOW
C_SLOPE = m.GREEN_C


def f(x: float) -> float:
    return 0.25 * x**2 - 0.5


def df(x: float) -> float:
    return 0.5 * x


class DerivativeTangent(m.Scene):
    def construct(self) -> None:
        title = m.Text("How steep is a curve?", font_size=38).to_edge(m.UP, buff=0.35)
        self.play(m.FadeIn(title, shift=m.DOWN * 0.2))

        # ---- beat 1: the curve
        self.next_section("Curve", notes="Here is a curve. Steepness changes as we move.")
        axes = m.Axes(x_range=[-4, 4, 1], y_range=[-1, 4, 1], x_length=8.0, y_length=4.4, tips=False).shift(m.DOWN * 0.2 + m.LEFT * 1.6)
        graph = axes.plot(f, x_range=[-4, 4], color=C_CURVE, stroke_width=5)
        self.play(m.Create(axes), run_time=1.2)
        self.play(m.Create(graph), run_time=1.5)
        self.wait(0.5)

        # ---- beat 2: the sliding tangent
        self.next_section("Tangent", notes="A tangent line touches the curve at one point; watch its slope.")
        x = m.ValueTracker(-3.0)
        dot = m.always_redraw(lambda: m.Dot(axes.c2p(x.get_value(), f(x.get_value())), color=C_TANGENT, radius=0.09))

        def tangent_line() -> m.Line:
            x0 = x.get_value()
            p0 = np.array([x0, f(x0)])
            slope = df(x0)
            a = axes.c2p(*(p0 - np.array([1.2, 1.2 * slope])))
            b = axes.c2p(*(p0 + np.array([1.2, 1.2 * slope])))
            return m.Line(a, b, color=C_TANGENT, stroke_width=4)

        tangent = m.always_redraw(tangent_line)
        readout = m.VGroup(
            m.MathTex(r"\text{slope} =", font_size=40),
            m.DecimalNumber(df(-3.0), num_decimal_places=2, font_size=44, color=C_SLOPE),
        ).arrange(m.RIGHT, buff=0.25).to_edge(m.RIGHT, buff=0.6).shift(m.UP * 1.2)
        number = readout[1]
        number.add_updater(lambda d: d.set_value(df(x.get_value())))
        self.play(m.FadeIn(dot), m.Create(tangent), m.FadeIn(readout))
        self.play(x.animate.set_value(3.0), run_time=7, rate_func=m.smooth)
        self.wait(0.5)

        # ---- beat 3: the slope is the derivative
        self.next_section("Derivative", notes="That slope, at every x, is the derivative.")
        self.play(x.animate.set_value(1.0), run_time=1.5)
        claim = m.MathTex(r"f'(x) = \tfrac{1}{2}x", font_size=52, color=C_SLOPE).next_to(readout, m.DOWN, buff=0.8)
        self.play(m.Write(claim))
        self.play(m.Indicate(number, color=C_SLOPE))
        self.wait(1.5)
