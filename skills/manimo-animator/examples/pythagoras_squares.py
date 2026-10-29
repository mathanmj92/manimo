"""The Pythagorean theorem as areas: the two small squares fill the big one.

One idea: a^2 + b^2 = c^2 is a statement about AREAS of squares built on the triangle's sides.
Beats: 1) the right triangle  2) a square on each side  3) their areas, then the equation.
"""

import numpy as np

import manimgx as m

C_A = m.BLUE_C
C_B = m.GREEN_C
C_C = m.YELLOW
C_TRI = m.GREY_B

SCALE = 0.5
# a 3-4-5 triangle with the right angle at the lower left; the three squares must all fit inside the frame
P_RIGHT = np.array([-0.6, -0.7, 0.0])
P_A = P_RIGHT + np.array([3 * SCALE, 0.0, 0.0])    # end of the horizontal leg (length 3)
P_B = P_RIGHT + np.array([0.0, 4 * SCALE, 0.0])    # end of the vertical leg (length 4)


def square_on(p: np.ndarray, q: np.ndarray, away_from: np.ndarray, color) -> m.Polygon:
    """The square built on segment p-q, on the side away from `away_from`."""
    edge = q - p
    normal = np.array([-edge[1], edge[0], 0.0])
    if np.dot(normal, (p + q) / 2 - away_from) < 0:
        normal = -normal
    return m.Polygon(p, q, q + normal, p + normal, color=color, fill_color=color, fill_opacity=0.35, stroke_width=3)


class PythagorasSquares(m.Scene):
    def construct(self) -> None:
        title = m.Text("The Pythagorean theorem, as areas", font_size=38).to_edge(m.UP, buff=0.35)
        self.play(m.FadeIn(title, shift=m.DOWN * 0.2))

        # ---- beat 1: the triangle
        self.next_section("Triangle", notes="A right triangle with legs a and b and hypotenuse c.")
        tri = m.Polygon(P_RIGHT, P_A, P_B, color=C_TRI, stroke_width=4)
        corner = m.Square(side_length=0.25, color=C_TRI, stroke_width=3).move_to(P_RIGHT + np.array([0.125, 0.125, 0.0]))
        self.play(m.Create(tri), m.Create(corner))
        label_a = m.MathTex("a", color=C_A, font_size=40).next_to((P_RIGHT + P_A) / 2, m.UP, buff=0.12)
        label_b = m.MathTex("b", color=C_B, font_size=40).next_to((P_RIGHT + P_B) / 2, m.RIGHT, buff=0.12)
        label_c = m.MathTex("c", color=C_C, font_size=40).next_to((P_A + P_B) / 2, m.UR, buff=0.05)
        self.play(m.Write(label_a), m.Write(label_b), m.Write(label_c))
        self.wait(1)

        # ---- beat 2: a square on every side
        self.next_section("Squares", notes="Build a square on each side.")
        centre = (P_RIGHT + P_A + P_B) / 3
        sq_a = square_on(P_RIGHT, P_A, centre, C_A)
        sq_b = square_on(P_RIGHT, P_B, centre, C_B)
        sq_c = square_on(P_A, P_B, centre, C_C)
        self.play(m.GrowFromCenter(sq_a), m.GrowFromCenter(sq_b))
        self.wait(0.5)
        self.play(m.GrowFromCenter(sq_c))
        self.wait(1)

        # ---- beat 3: the areas
        self.next_section("Areas", notes="The two small areas add up to the big one.")
        area_a = m.MathTex("a^2", color=C_A, font_size=44).move_to(sq_a)
        area_b = m.MathTex("b^2", color=C_B, font_size=44).move_to(sq_b)
        area_c = m.MathTex("c^2", color=C_C, font_size=44).move_to(sq_c)
        self.play(m.Write(area_a), m.Write(area_b), m.Write(area_c))
        self.wait(1)
        equation = m.MathTex("a^2", "+", "b^2", "=", "c^2", font_size=64).to_edge(m.DOWN, buff=0.45)
        equation[0].set_color(C_A)
        equation[2].set_color(C_B)
        equation[4].set_color(C_C)
        self.play(m.TransformFromCopy(area_a, equation[0]), m.Write(equation[1]), m.TransformFromCopy(area_b, equation[2]),
                  m.Write(equation[3]), m.TransformFromCopy(area_c, equation[4]), run_time=2)
        self.play(m.Circumscribe(equation, color=m.WHITE))
        self.wait(1.5)
