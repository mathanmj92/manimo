# Visuals for theory: pictures, motion and 3D

Every abstract symbol gets a picture. Calls below were run with `manimgx inspect` (2D scenes clean; 3D scenes render but are not layout-checked). Worked example: `theory_particle_in_a_box_manimo.py`.

## 1. Idea to picture
| Idea | Picture |
|---|---|
| A function, a law | Graph on `m.Axes` with a `ValueTracker` sweep of one parameter |
| A probability or distribution | Shaded area (`axes.get_area`), histogram from fixed-seed samples, bars that grow as samples arrive |
| An integral | The area, shaded, with the limits marked |
| A derivative | Tangent line and slope triangle moving along the curve |
| A quantised set | Energy ladder (horizontal levels) with the allowed states drawn on each level |
| A wave | Moving curve, nodes marked as dots, wavelength braced |
| A complex quantity | Phase-coloured curve, or a point on `m.ComplexPlane`, or a helix in 3D |
| A vector field | `m.ArrowVectorField` or `m.StreamLines` (2D) or arrows in 3D |
| A symmetry | Apply it: rotate, reflect, show the picture is unchanged |
| A limit | A sequence of curves approaching one shape (`ReplacementTransform`) |
| A many-particle system | Dots in a box moving with a fixed seed, plus the histogram of speeds or positions |
| A state space | Phase space (x, p), Bloch sphere, energy-level diagram |
| A conservation law | Two bars (before, after) or a stacked bar whose total stays fixed |

## 2. 2D idioms (preferred: the layout check can verify them)
- **Layout**: figure on the left (x from -6.3 to 0.3), equation panel on the right (left edge 0.9, width 5.4), caption at the bottom, title at the top. For full-width pictures, put the equation strip below.
- **Axes**: `m.Axes(x_range=..., y_range=..., x_length=5, y_length=3.2, tips=False, axis_config={"include_ticks": False, "include_numbers": False})`; add your own labels (`0`, `L`). `tips=False` keeps arrow heads from colliding with curves.
- **Plot**: `axes.plot(lambda x: ..., x_range=[a, b, step], color=..., stroke_width=5)`. Use a step of about 0.002 to 0.005 for fast ripples. Area: `axes.get_area(graph, x_range=[a, b], color=..., opacity=0.35)`.
- **Parameter sweep**: `t = m.ValueTracker(v0)`; `curve = m.always_redraw(lambda: axes.plot(lambda x: f(x, t.get_value()), ...))`; play `m.AnimationGroup(t.animate.set_value(v1), run_time=8, rate_func=m.linear)` inside `self.say` while the voice explains what to watch. Make the thing to watch change colour (a dot that turns green when a condition holds).
- **Discrete states**: build each state as a `VGroup`, change with `m.ReplacementTransform`.
- **Histogram**: `rng = np.random.default_rng(1)`; `np.histogram`; one `m.Rectangle` per bin placed with `.move_to(point, m.DOWN)`; reveal in batches to show the law of large numbers.
- **Particles**: positions from a fixed seed, `add_updater` that reflects at the walls; clear updaters before transforming.
- **Phase-coloured complex wave** (colour = phase, height = modulus):
```python
import colorsys

def phase_color(z: complex):
    hue = (math.atan2(z.imag, z.real) / (2 * math.pi)) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 1.0)
    return m.rgb_to_color([r, g, b])

def complex_curve(axes, f, x_range, steps=240, width=5):
    xs = np.linspace(x_range[0], x_range[1], steps + 1)
    return m.VGroup(*[m.Line(axes.c2p(a, abs(f(a))), axes.c2p(b, abs(f(b))), color=phase_color(f(a)), stroke_width=width)
                      for a, b in zip(xs[:-1], xs[1:])])
```
  Explain the colour wheel on screen the first time (red = real positive, and so on), and say that only differences of phase matter.
- **Vector fields**: `m.ArrowVectorField(lambda p: ..., x_range=[...], y_range=[...])`, then `.scale(...)` and `.move_to(...)`; keep the arrows few and large enough to read (the default can come out tiny).
- **Equation transformations**: `m.TransformMatchingTex(old, new)` for algebra in place; `m.TransformFromCopy(figure_part, symbol)` for "this becomes that".
- **Attention**: `m.Indicate`, `m.Circumscribe`, `m.Flash`; fade the rest to low opacity instead of adding clutter.
- **Text size**: at least 22 pt; labels under about 22 pt are reported as tiny.

## 3. When to use 3D (the rule)
Use 3D only when the third dimension carries meaning: a surface z = f(x, y) (probability density of a 2D system, a potential surface), a sphere (Bloch sphere, a unit sphere of directions), a vector field in space, a helix (a complex exponential as a corkscrew), orbitals or charge distributions, a phase-space surface. Otherwise stay 2D. For forces in space, use the oblique 2D projection of the problem scenes (`problem_cables_3d_resultant_manimo.py`), because the layout check works there.

### Verified 3D calls (ManimGX)
`m.ThreeDScene`, `self.set_camera_orientation(phi=..., theta=...)`, `m.ThreeDAxes(x_range, y_range, z_range, x_length, y_length, z_length)`, `axes.c2p(x, y, z)`, `m.Surface(lambda u, v: axes.c2p(u, v, f(u, v)), u_range=[..], v_range=[..], resolution=(34, 34), fill_opacity=0.75).set_color(...)`, `m.ParametricFunction(lambda t: axes.c2p(...), t_range=[a, b, step])` (helix), `m.Sphere(radius=1, resolution=(18, 18)).set_color(...).set_opacity(0.25)`, `m.Arrow3D(start=np.array([...]), end=np.array([...]))`, `m.Dot3D`, `m.Line3D`, `self.add_fixed_in_frame_mobjects(...)`, `self.begin_ambient_camera_rotation(rate=0.15)`, `self.stop_ambient_camera_rotation()`, `self.move_camera(phi=..., theta=..., run_time=3)`. `self.say(...)` works in a 3D scene with the same bracketed spans.

### Rules for 3D scenes
1. **Text and equations fixed in the frame**: create them, `self.add_fixed_in_frame_mobjects(*items)`, then `self.remove(*items)` and bring them in with `FadeIn` when spoken. Keep them in the corners, away from the surface.
2. **The layout check is skipped** ("not checked (a 3D scene)"). Read the storyboard frames: nothing outside the frame, no label on the surface, nothing hidden behind it. Move the camera or the labels if needed.
3. **Camera discipline**: start from a clear angle (phi about 60 degrees, theta about -55), rotate slowly (rate at most 0.2) only while nothing precise is being read, stop the rotation while a detail is explained, finish on a purposeful view (for example straight down to show nodes as a grid).
4. **Fewer, bigger objects**: one surface at a time (`FadeOut` the old before `FadeIn` the new); resolution 30 to 40 is smooth enough; use opacity 0.7 to 0.8 and one colour per state.
5. **Axes are a scaffold**: hide ticks and numbers (`axis_config={"include_ticks": False, "include_numbers": False}`) and label only what matters.
6. **Always name what the height means** ("probability density") in a fixed caption.

### Typical 3D scenes
- Bloch sphere: a translucent `Sphere`, an equator `m.Circle`, an `Arrow3D` for the state, rotated by updating its end point.
- Orbitals and probability clouds: a `Surface` of |psi|^2 over a plane, or radial plots in 2D plus an angular `Surface` r = |Y(theta, phi)|.
- 2D wells and membranes: a `Surface` of |psi|^2 (done in the example), nodes seen from above.
- A complex exponential: `ParametricFunction` helix (real along y, imaginary along z).
- A field in space: arrows on a coarse grid, or field lines as `ParametricFunction` curves.
- Surface of an energy landscape or phase-space density with a marker moving on it.

## 4. Motion and pacing
- Typical `run_time` 1 to 1.5 s, key moments 2 to 3 s; parameter sweeps 6 to 9 s with the voice telling the student what to watch.
- A pause of 0.5 s after a small reveal, 1.5 s after a big one, 2 s at the end.
- Time evolution slowed to a human pace, and said to be slowed.
- One moving thing at a time unless the point is a comparison.

## 5. Colour table (write it at the top of the file and keep it)
Neutral defaults: the main object `BLUE_C`; probability or the quantity measured `YELLOW`; energy and answers `GREEN`; nodes and special points `ORANGE`; heat or temperature `RED_C`/`ORANGE`; guides and captions `GREY_B`; mistakes and forbidden regions `RED_C`. Same quantity, same colour, from picture to equation. No more than four or five colours in a scene.
