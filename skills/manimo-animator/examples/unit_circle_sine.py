"""Where the sine wave comes from: a point circling a unit circle draws it.

One idea: the height of a point going round a circle IS the sine wave.
Beats: 1) the circle and its moving point  2) its height as a line  3) the wave being traced out.
"""

import numpy as np

import manimgx as m

# one colour per idea, used everywhere
C_POINT = m.YELLOW
C_CIRCLE = m.BLUE_C
C_WAVE = m.GREEN_C
C_GUIDE = m.GREY_B

R = 1.5                                    # circle radius in scene units
CIRCLE_C = np.array([-3.6, 0.0, 0.0])      # circle centre, left half of the frame
WAVE_X0 = 0.0                              # where the wave starts, right half of the frame
WAVE_W = 5.6                               # width of one full turn on screen


class UnitCircleSine(m.Scene):
    def construct(self) -> None:
        title = m.Text("Where does a sine wave come from?", font_size=38).to_edge(m.UP, buff=0.35)
        self.play(m.FadeIn(title, shift=m.DOWN * 0.2))

        # ---- beat 1: the circle and its point
        self.next_section("Circle", notes="Say: a point goes round a circle at steady speed.")
        circle = m.Circle(radius=R, color=C_CIRCLE).move_to(CIRCLE_C)
        axes_h = m.Line(CIRCLE_C + m.LEFT * (R + 0.5), CIRCLE_C + m.RIGHT * (R + 0.5), color=C_GUIDE, stroke_width=2)
        axes_v = m.Line(CIRCLE_C + m.DOWN * (R + 0.5), CIRCLE_C + m.UP * (R + 0.5), color=C_GUIDE, stroke_width=2)
        angle = m.ValueTracker(0.0)

        def point_pos() -> np.ndarray:
            a = angle.get_value()
            return CIRCLE_C + R * np.array([np.cos(a), np.sin(a), 0.0])

        dot = m.always_redraw(lambda: m.Dot(point_pos(), radius=0.1, color=C_POINT))
        radius_line = m.always_redraw(lambda: m.Line(CIRCLE_C, point_pos(), color=C_POINT, stroke_width=3))
        self.play(m.Create(axes_h), m.Create(axes_v), m.Create(circle))
        self.play(m.FadeIn(dot), m.Create(radius_line))
        self.play(angle.animate.set_value(np.pi / 3), run_time=1.5)
        self.wait(0.5)

        # ---- beat 2: its height
        self.next_section("Height", notes="Say: look only at how high the point is.")
        height = m.always_redraw(
            lambda: m.Line(
                [point_pos()[0], CIRCLE_C[1], 0.0], point_pos(), color=C_WAVE, stroke_width=5
            )
        )
        caption = m.Text("its height", font_size=26, color=C_WAVE).to_edge(m.DOWN, buff=0.5).shift(m.LEFT * 3.6)
        self.play(m.Create(height), m.FadeIn(caption))
        self.wait(1)

        # ---- beat 3: the wave being traced
        self.next_section("Wave", notes="Say: plot that height against time and the sine wave appears.")
        wave_axis = m.Line([WAVE_X0, 0.0, 0.0], [WAVE_X0 + WAVE_W + 0.4, 0.0, 0.0], color=C_GUIDE, stroke_width=2)
        start_angle = angle.get_value()

        def wave_point(a: float) -> np.ndarray:
            return np.array([WAVE_X0 + WAVE_W * (a - start_angle) / (2 * np.pi), R * np.sin(a), 0.0])

        trace = m.always_redraw(
            lambda: m.ParametricFunction(
                lambda t: wave_point(start_angle + t),
                t_range=[0.0, max(angle.get_value() - start_angle, 0.001), 0.05],
                color=C_WAVE,
                stroke_width=5,
            )
        )
        tip = m.always_redraw(lambda: m.Dot(wave_point(angle.get_value()), radius=0.08, color=C_WAVE))
        link = m.always_redraw(
            lambda: m.DashedLine(point_pos(), wave_point(angle.get_value()), color=C_GUIDE, stroke_width=2)
        )
        self.play(m.Create(wave_axis), m.FadeOut(caption))
        self.add(trace, tip, link)
        self.play(angle.animate.set_value(np.pi / 3 + 2 * np.pi), run_time=6, rate_func=m.linear)
        self.wait(1)

        formula = m.MathTex(r"y = \sin\theta", font_size=48, color=C_WAVE).to_edge(m.DOWN, buff=0.5).shift(m.RIGHT * 2.8)
        self.play(m.Write(formula))
        self.wait(1.5)
