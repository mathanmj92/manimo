# First-year, exam-safe mode (students fresh from class 12)

Use this mode whenever the audience is first-year engineering students, or the user says "exam", "marks", "beginners", "they miss steps". These students lose marks for steps a teacher thinks are obvious, so nothing an examiner expects may be skipped, and every trap must be named before it is stepped on. Worked example: `problem_2_1_resultant_hook_manimo.py` in the workspace root (read it before writing).

## The rules
1. **Read the figure aloud, with the trap.** List every angle and say from which line it is measured. If an angle is between two forces and not from the reference line, show it in its own colour and add the angles to get the direction from the reference (30 + 45 = 75). Mark the likely mistake in words ("many students use 45 here").
2. **Write Given / Find / Method first**, on screen, in the form to be copied into the answer book. Give units everywhere. Name the reference line and the sign or angle convention.
3. **Solve it the way it is solved on paper.** First-year students do not use graph sheets, rulers or protractors for these problems, so do NOT build a scale drawing unless the user explicitly asks for one. "Determine graphically" in a textbook means: draw a neat labelled sketch with the right angles (lengths need not be to scale), then apply the laws. For concurrent forces: (a) parallelogram law, R^2 = F1^2 + F2^2 + 2 F1 F2 cos(alpha) with alpha the angle between the forces when both start at the same point (plus cosine), and the direction from tan(beta) = F1 sin(alpha) / (F2 + F1 cos(alpha)), shown by dropping a perpendicular and naming base and height; (b) triangle law: forces head to tail, the angle between the sides is 180 - alpha (use angle chasing: adjacent angles of a parallelogram add to 180), law of cosines with a minus sign and a negative cosine, law of sines for the direction. Show that both laws give the same number because cos(180 - alpha) = -cos(alpha). Redraw the figure as a clean sketch; keep true angles and proportions, but state no scale.
4. **Every formula in three lines**: the general law with symbols, then the substitution with numbers, then the arithmetic. Say the law's name. Show intermediate numbers to 4 significant figures and the final to 3 or 4. Units on every line.
5. **Signs and supplements.** When a construction changes an angle (head-to-tail triangle: the angle between the sides is 180 minus the angle between the forces), draw it and say why. When a trig value is negative (cos 135 = -0.7071), say it, show the value on screen, and say "minus a negative is a plus".
6. **Calculator mode.** Say "degree mode" wherever an angle is typed in.
7. **Direction is part of the answer.** State magnitude, angle, from which line, and which way (above/below, left/right, clockwise).
8. **Verify by a second, independent method** (for forces: law of cosines and sines, then components). Say that the answers agree, and why the two laws give the same number.
9. **End with a model answer page**: exactly what to write in the exam (Given, neat sketch, law with substitution, direction formula, checks, boxed answer with unit and direction) beside "the traps" in red (3 to 5 short items).
10. **Narration for beginners**: slower, define each word the first time (resultant, vector, head and tail), say every number and unit, say "step one, step two", and ask a question before a result ("will R be exactly 25?"). One idea per sentence. Say what to write, not only what to understand.

## Beats to use (adapt to the topic)
1 read the figure and its traps, 2 given / find / method, 3 method A on paper (sketch, law, substitution, arithmetic, direction with angle finding), 4 method B on paper (triangle, supplementary angle, law, direction), 5 a quick independent check (components), 6 model answer and traps. A first-year problem runs 4 to 6 minutes; that is right.

## Checklist before you answer
- [ ] Every angle is stated with its reference line; the "between the forces" angle is converted.
- [ ] Given / Find / Method shown before the drawing.
- [ ] A neat sketch with true angles; no scale drawing or instruments unless asked; the parallelogram and the triangle drawn from the same sketch.
- [ ] Angle chasing shown (45 between the forces; 30 + 45 = 75; triangle angle 180 - 45 = 135; theta = 30 + beta).
- [ ] Each formula: law name, symbols, numbers, arithmetic, units.
- [ ] Negative trig values and supplementary angles explained on screen.
- [ ] Answer has magnitude, unit, angle, reference line and sense.
- [ ] A second method confirms it.
- [ ] Model answer page with the traps.
- [ ] Numbers in the scene come from the same Python formulas; assertions agree across methods.
- [ ] Spoken numbers and units are spelled out; spans equal animations.

## Forces in space (3D cables, struts, unit vectors)
Worked example: `problem_cables_3d_resultant_manimo.py` in the workspace root. Use this order, one step per beat, nothing skipped:
1. **Read the 3D figure**: say what each dimension measures (along the wall, up, out from the wall), mark the unused points (stake D), and show the unit conversion the problem gives (27 ft = 9 m, ...). Check your reading against the original numbers when they are known (here AB = (-11, 8, -16) ft and AC = (16, 8, -16) ft give lengths 21 and 24 ft, which confirms the reading).
2. **Axes and coordinates**: choose an origin at a corner, name x, y, z (right-handed, z out of the wall), and read the coordinates of every point with a one-line reason each.
3. **Vectors = head minus tail** with the subtraction written out per component.
4. **Length** by the distance formula (all three components; negative squared is positive).
5. **Unit vector** = vector / length, with the check that the squares of its components add to 1.
6. **Force vector** = tension x unit vector, in kN, 3 decimals; draw the arrows on the figure.
7. **Resultant** = add component by component, keeping signs; use the sum of the rounded numbers a student would write, and assert in code that it equals the rounded exact value (otherwise use 4 decimals).
8. **Magnitude** = square root of the sum of the squares.
9. **Direction** = direction cosines cos(theta_i) = R_i / R, arccos in degree mode, all three angles, angle above 90 degrees for a negative component, and the check that the cosines squared add to 1.
10. **Model answer and traps** (head minus tail; all three components; keep signs; degree mode and the cos-squared check; units and all three angles).
Drawing the 3D figure: use a fixed oblique projection with 2D mobjects (screen = origin + x*EX + y*EY + z*EZ, for example EX=(0.55,0.20), EY=(0,0.60), EZ=(0.30,-0.28)) so layout checks still work; draw the solid (wall) as a filled polygon, cables as lines, dimension arrows, and dashed coordinate paths (along x, then along z) to show how a point's coordinates are read. Fade the helper paths before drawing force arrows from the same point so labels do not collide.

## Reveal rules for every step
Read `references/reveal-and-sync.md`: each equation is revealed term by term, left to right, in step with the spoken words (fractions: numerator, then denominator; integrals left to right); lists appear one item per sentence; and the part of the figure being used (an edge, the box, the right triangle with its angle, the unit arrow) is highlighted while it is worked on.

## Equilibrium of a particle in space (cables, a hanging load, a pushing force)
Worked example: `problem_cylinder_cables_equilibrium_manimo.py` in the workspace root. Order, nothing skipped:
1. Read the figure and each dimension (what is along the wall, up, out from it); mass in kg is NOT a force: W = m g in newtons, drawn downwards.
2. Axes and coordinates of every point, then the free-body diagram of the joint: ALL forces on it (every cable tension, the applied force, the weight) and the statement "at rest, so the sum is zero".
3. Vectors by head minus tail, lengths, unit vectors (4 decimals, squares add to 1), each tension = T times its unit vector.
4. The vector equation split into three scalar equations (sum of Fx, Fy, Fz = 0), each shown with the x, y and z legs of the forces in the figure: equal and opposite legs balance, the two upward legs hold up the weight, the legs towards the wall are balanced by the applied force.
5. Solve in the order that keeps the unknowns few: the equation with two unknowns first (x), substitute into the next (y), then the last (z) gives the remaining unknown; show the hand steps with the same 4-decimal coefficients a student would use, keep one decimal in the middle, round the answers at the end, and assert in code that the hand steps match the exact solve.
6. Check by substituting the rounded answers back into all three equations (small rounding remainders are normal and are said aloud), plus one physical sanity remark.
7. Model answer and traps (kg to N; all four forces; cables pull towards the wall so their z components are negative and the pushing force is positive; solve x first; substitute back and give units and all answers).
Figure tip: when one dimension (here 1.2 m out of the wall) is small, enlarge its screen scale (EZ) so the joint is not a blob, keep labels of forces off the wall region or drop them (colour already matches the equation), and move the panel left edge right if a dashed edge runs into it.
