# Visual language for mechanics, physics and kinematics

Consistent encoding is what makes these animations teach. Use these colours for the same quantity in every scene, and define them as constants.

| Quantity | Colour | Notes |
|---|---|---|
| Body, mass, beam | `BLUE_C` fill 0.35, `BLUE_C` stroke | the thing being studied |
| Surface, ground, wall, support | `GREY_B` | thin hatch marks below the surface |
| Weight / gravity `W = mg` | `RED_C` | always straight down |
| Normal reaction `N`, support reactions | `GREEN_C` | perpendicular to the surface |
| Friction `f`, drag, resistance | `ORANGE` | along the surface, opposite to motion (tendency) |
| Applied force `F`, tension `T` | `YELLOW` | tension along the rope, pulling away from the body |
| Velocity `v` | `TEAL_C` | arrow from the body, length ~ speed |
| Acceleration `a` | `PURPLE_B` | different arrowhead feel: thinner, offset from the body |
| Result / answer | `GREEN` + `SurroundingRectangle` | |
| Guides, axes, dimensions, angles | `GREY_B` / `GREY_C` | thin, dashed for projections |
| Moments / torque | `PINK` | curved arrow around the point |

## Drawing rules
- **Scale**: pick one length scale and state it (`1 m = 0.9 units`, `1 kN = 0.35 units`). Force arrow length is proportional to magnitude. Keep every arrow between 0.8 and 2.6 units long, and add the value in the label (`N = 84.9 N`), not only the symbol.
- **Arrow tails** start at the point of application (the contact point, or the centre of mass for weight). Use `m.Arrow(start, end, buff=0, color=..., stroke_width=6)`.
- **Labels** sit beside the arrow tip, 0.12 to 0.2 away, on the side away from other arrows. Use `MathTex` with the symbol first (`N`), then replace with the value when substituting numbers.
- **Components**: dashed `DashedLine` projections plus thin component arrows in a lighter shade of the force colour, grown from the force arrow tip. Mark the angle with `Angle` and a label `\theta`.
- **Axes**: draw the chosen x and y axes as two small arrows at the corner of the diagram, labelled `x`, `y`. For inclines, tilt the axes (x along the slope, y perpendicular). Say "choose axes along the slope" in the set-up beat.
- **Free-body diagram**: show the body alone as a dot or small block, all forces from its centre, after fading the environment. Add forces one at a time, in this order: weight, normal, friction, applied/tension.
- **Motion**: move bodies with a `ValueTracker` and `always_redraw` or `updater`, using the real equation (`s = v0 t + a t^2 / 2`), so the picture and the maths agree. Do not use arbitrary easing for physical motion; use `rate_func=m.linear` unless the physics says otherwise.
- **Time and graphs**: for kinematics put a small `Axes` for x-t, v-t or a-t beside the scene with a moving `Dot` and a traced curve. Shade the area under v-t when displacement is the answer.
- **Sign convention**: show it once in the set-up beat ("take up and right as positive"), then keep it.
- **Units** are always written in answers and in substituted equations (`\text{N}`, `\text{m/s}^2`). Use `g = 9.81 m/s^2` unless the problem says otherwise.

## Setups and how to show them
- **Particle on an incline**: draw the incline as a right triangle, the block as a rotated square (`rotate(theta)`), weight straight down, resolve `mg` into `mg sin(theta)` along the slope and `mg cos(theta)` into the surface. Friction up the slope if the tendency is down.
- **Pulleys and ropes**: ropes are thin lines in `GREY_B`; same tension in an ideal rope (say it). Draw the constraint ("rope length is fixed so the blocks have equal speed").
- **Beams and trusses**: pin support = triangle, roller = triangle on a circle, fixed = hatched wall. Loads as arrows with value, distributed loads as a row of arrows under a bracket plus the equivalent point load at the centroid. Equilibrium in the order: `Sum Fx = 0`, `Sum Fy = 0`, `Sum M = 0` about a smart point (the one that removes unknowns), saying why.
- **Projectile / kinematics**: split velocity into components, run both motions in parallel with a trace; dashed vertical line at the top, mark `v_y = 0` there.
- **Circular motion / rotation**: show the radius, velocity tangent, acceleration toward the centre. Use `\omega`, `\alpha` with the same colours as `v`, `a`.
- **Energy / work**: bar chart of kinetic and potential energy that changes with a tracker; the total stays constant (a fixed outline).
- **Fluid / thermo / waves / circuits** (physics beyond mechanics): same rules: draw the physical set-up, one quantity per colour, build the law from the picture, solve one step at a time.

## Equation style for the solve beat
- Write the general law first (`\sum F_x = ma_x`), then the version for this problem, then substitute numbers, then simplify, then the answer. Each is a new line that replaces the previous one in the same place (`TransformMatchingTex` or `ReplacementTransform`), so the student sees what changed.
- Split `MathTex` into parts so you can colour the symbols with the arrow colours: `m.MathTex("N", "-", "mg\\cos\\theta", "=", "0")` then `eq[0].set_color(C_NORMAL)`.
- Keep a single column of at most 3 equations visible. Fade the oldest, or move it up and shrink it.
- Round only the final answer, to 3 significant figures, unless the problem gives fewer.

## Common mistakes to bake into the checks
Forgetting the sign of friction, using `sin` and `cos` the wrong way round on an incline, mixing degrees and radians (`math.sin(math.radians(...))`), mass in grams, forgetting the normal force changes with an applied angle, taking moments about a point and still using the wrong sign. Teach these as optional "Common mistake" callouts (see the pipeline file).
