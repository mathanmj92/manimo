# Copy-paste helpers for problem animations (ManimGX; for Manim CE drop the `m.` prefix)

Scene files must stay single-file and runnable, so paste the helpers you need at the top of the file. All of these are tested in the files in `examples/`.

## Compute first, animate second
```python
import math
import numpy as np
import manimgx as m

MASS = 10.0   # kg   <- the givens, copied exactly from the problem
THETA = math.radians(30.0)
NORMAL = MASS * 9.81 * math.cos(THETA)     # the solution, computed once
# then write results into MathTex with f-strings: rf"N={NORMAL:.1f}\ \mathrm{{N}}"
```
Doubling braces in an `rf"..."` string (`{{ }}`) gives literal LaTeX braces. The animation can then never disagree with the maths.

## Force arrow with length proportional to the force
```python
FORCE_SCALE = 0.02    # 1 N = 0.02 screen units

def force_arrow(origin: np.ndarray, direction: np.ndarray, newtons: float, color) -> m.Arrow:
    end = origin + direction * newtons * FORCE_SCALE
    return m.Arrow(origin, end, buff=0, color=color, stroke_width=6, tip_length=0.2)
```
Use `tip_length=0.15` or less for arrows shorter than 0.5 units.

## Angle arc and label between two rays (any geometry or mechanics figure)
```python
def angle_arc(vertex, p, q, radius, color) -> m.Arc:
    a1 = math.atan2(p[1] - vertex[1], p[0] - vertex[0])
    a2 = math.atan2(q[1] - vertex[1], q[0] - vertex[0])
    delta = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    return m.Arc(radius=radius, start_angle=a1, angle=delta, arc_center=vertex, color=color, stroke_width=4)

def angle_label_point(vertex, p, q, distance):
    u = (p - vertex) / np.linalg.norm(p - vertex) + (q - vertex) / np.linalg.norm(q - vertex)
    return vertex + distance * u / np.linalg.norm(u)
```

## Point on a slope, outward normal, rotated block
```python
DOWN_SLOPE = np.array([math.cos(THETA), -math.sin(THETA), 0.0])    # incline descending to the right
OUT_NORMAL = np.array([math.sin(THETA), math.cos(THETA), 0.0])
block = m.Square(0.8, color=m.BLUE_C, fill_opacity=0.35).rotate(-THETA).move_to(point_on_slope + OUT_NORMAL * 0.4)
```
For an incline that descends to the left, mirror the x components and rotate by `+THETA`.

## Motion that follows a formula (not an easing curve)
```python
t = m.ValueTracker(0.0)
body.add_updater(lambda mob: mob.move_to(start + direction * 0.5 * accel * t.get_value() ** 2))
self.play(t.animate.set_value(1.2), run_time=2.5, rate_func=m.linear)
body.clear_updaters()
```
Run time equals physical time only if you set it so; say "slowed down" if you scale it.

## Trajectory on axes
```python
axes = m.Axes(x_range=[0, 45, 10], y_range=[0, 10, 5], x_length=7.0, y_length=3.0,
              axis_config={"color": m.GREY_B, "include_ticks": False, "include_tip": False})
path = m.ParametricFunction(lambda t: axes.c2p(vx * t, vy * t - 0.5 * g * t * t), t_range=[0, t_end], color=m.BLUE_C)
self.play(m.MoveAlongPath(ball, path), m.Create(path), run_time=2.5, rate_func=m.linear)
```

## Supports for beams
Pin: `m.Triangle(...).scale(0.28)` under the beam. Roller: the same plus `m.Circle(radius=0.1)` under it. Fixed support: a tall `m.Rectangle` with short diagonal `m.Line` hatch marks. Distributed load: a row of short down arrows from `m.VGroup(*[m.Arrow(...) for ...])` plus a `m.Brace` or a top line, and then the equivalent point load at the centroid (a different colour).

## Dimension line
```python
dim = m.DoubleArrow(left, right, buff=0, color=m.GREY_B, stroke_width=3, tip_length=0.15)
dim_label = m.MathTex(r"2\ \mathrm{m}", font_size=30, color=m.GREY_B).next_to(dim, m.DOWN, buff=0.12)
```

## Layout recipe: figure left, solution right
Figure inside x -6.3..0.7; solution column centred at `m.RIGHT * 3.4` (about 5 units wide, font 30 to 36); "Find:" caption at the upper right under the title; "Given" line at the bottom left, `GREY_B`. Keep at most 3 or 4 equations in the column and `FadeOut` older ones before adding more.

## Gotchas found while testing
- A `SurroundingRectangle` around a `VGroup` of equations that are not adjacent will cover the equation between them: box each result on its own.
- Axes labels placed on a line that the arrows cross trigger "arrow runs through the text": put axis arrows in empty space (above the figure).
- Small labels (under about 22 pt at 1080p) are reported: use `font_size` 28 or more for anything a student must read, 24 for secondary captions.
- Index into `MathTex` parts (`eq[0]`, `eq[2]`) only when you split the string into explicit parts: `m.MathTex("N", r"-mg\cos\theta=0")`. Indexing glyphs inside a single string breaks on `\sin`, `\frac` and `\theta`.
- `manimgx inspect` writes storyboard PNGs next to the scene file: delete them when done, or run it from the folder where they belong.
