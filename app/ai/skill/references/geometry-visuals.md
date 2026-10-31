# Visual language for geometry problems

## Reading a geometry figure
List: points and their labels, given lengths, given angles (with which arc or tick marks mean equal), right angle marks, parallel marks, tangent/circle facts, what to find. If the image has no scale, do not guess lengths from pixels: use the stated numbers, or build the figure from the constraints (so it is true for the given data).

## Build the figure from the data, not by eye
Compute coordinates with `math`/`numpy` from the givens (law of cosines, circle centres, intersection of lines) so the drawing is exactly consistent. For a triangle with sides a, b, c place `A` at the origin, `B = (c, 0)`, `C = (b cos A, b sin A)`. For circle problems place the centre first and put points at angles. Then scale and move the whole figure with one `VGroup` so it fits the frame (stay within x -6.3..6.3, y -3.4..3.4; a figure beside a solution panel should stay in x -6.3..0.5).

## Drawing rules
- Points: `Dot` plus a letter label 0.15 away on the outside of the figure (away from the centroid).
- Known data in `BLUE_C`/`GREY_B`; the unknown in `YELLOW` (a `?` or `x` label); derived angles/lengths in `GREEN_C` as they are found; auxiliary construction lines dashed in `TEAL`.
- Angles: `Angle(line1, line2, radius=0.5)` with a label `\alpha` inside the arc; equal angles share a colour and the same number of arcs. Right angles with `RightAngle`.
- Equal lengths: tick marks across the segments (small perpendicular `Line`s); parallel lines: arrowheads `>` drawn on them.
- Areas: fill regions with `fill_opacity=0.3`; to show subtraction, fill the big shape then overlay the removed part in the background colour or a hatched red.
- Construction steps appear one at a time with `Create`; say why ("draw the radius to the point of tangency"). Always state the theorem name or fact in 2 to 5 words when you use it ("angles in a triangle sum to 180", "tangent is perpendicular to radius", "inscribed angle is half the central angle", "similar triangles: same ratios").

## Solve beat
1. Highlight what you know (`Indicate`, `Circumscribe`).
2. Pick the fact; show it on the figure (`ApplyWave`/`Flash` on equal parts).
3. Write the equation under the figure built from the highlighted parts (`TransformFromCopy`).
4. Solve in one algebra step per animation, in place.
5. Put the result back on the figure in green, then `SurroundingRectangle` the final answer with units (degrees, cm, cm^2).
6. Optional: a second method or a `ValueTracker` "does it still work if we drag this point?" to show it is a general fact.

## Typical techniques worth animating
Angle chasing; the Pythagorean theorem and triples; similar triangles by scaling one onto the other (`ReplacementTransform` with a scale and rotate); area by decomposition and rearrangement (cut and move pieces); circle theorems (inscribed angle, tangent-chord, power of a point) with a dragged point; trigonometric height-and-distance by drawing the right triangle first; coordinate geometry (place on an `Axes`, compute distances/midpoints/slopes as the equations appear); solids (use `ThreeDScene` with `Prism`, `Cylinder`, `Sphere`; unfold nets when the surface area is asked).
