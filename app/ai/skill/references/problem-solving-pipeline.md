# Solve a problem, then teach it (image or text in, step-by-step animation out)

Use this when the user gives a problem (a photo, a screenshot, a textbook page or typed text) in engineering mechanics, engineering physics, kinematics, Newtonian mechanics or geometry, and wants it solved step by step as a 3Blue1Brown-style animation a teacher can play in class.

## Stage 1: Read the problem (from an image)
Look at the image carefully and write down, before any code:
- **Given**: every number with its unit (`m = 10 kg`, `theta = 30 deg`, `L = 6 m`). Copy values exactly; never round them.
- **Find**: what is asked, with the symbol.
- **Figure**: what the diagram shows (bodies, surfaces, supports, ropes, pulleys, angles, dimensions, loads, which way is "up").
- **Assumptions** stated or implied (frictionless, massless rope, rigid body, g = 9.81 m/s^2, small angle).
If something is unreadable or ambiguous (a blurred number, a missing angle), say which item and what you assumed. Ask only if the answer changes with the guess; otherwise state the assumption on screen in the first beat and in the reply.

## Stage 2: Solve it completely on paper first
Do the full solution in plain numbers before writing any animation. Keep a table of every intermediate result. Then **check it**:
- Units on both sides of every equation agree.
- Plug the answer back into the original equations.
- Limit or sanity check (a smooth incline with `theta = 0` gives `a = 0`; reactions sum to the load; angles in a triangle sum to 180 deg).
- Do the arithmetic in Python (`math`) inside your head-check or compute it in the scene with the same formulas, so the animation's numbers cannot disagree with the answer.
Never animate a number you have not verified. If the checks fail, redo the solution before animating.

## Stage 3: Choose the method the textbook would use
Mechanics: draw the free-body diagram (FBD), choose axes, write equilibrium or `F = ma`, solve. Energy or momentum methods only when they are simpler or the problem asks. Kinematics: list knowns/unknown, pick the equation (constant acceleration set, or area under the v-t graph), solve. Geometry: state the theorem used at each step. Name the principle on screen in 2 to 4 words ("Sum of forces along x = 0").

## Stage 4: Storyboard (always these beats, in this order)
1. **Problem** (4 to 8 s): redraw the figure cleanly from the image, with given values labelled. Show a one-line "Find: ..." caption. Do not paste the photo; redraw it so every part can move and be coloured. Use `ImageMobject` only if the user asks to show the original image.
2. **Model** (3 to 6 s): reduce to the physical model. Fade the scenery, keep the body; say the assumptions in short chips (`frictionless`, `g = 9.81`).
3. **Diagram** (5 to 10 s): add the free-body diagram or the labelled geometry one item at a time with a `Create`/`GrowArrow`, label after the arrow. Use the colour code in `mechanics-visuals.md`.
4. **Set-up** (4 to 8 s): choose axes (draw them), resolve vectors into components (dashed component arrows grow out of the force arrow), then write the governing equation built from the picture (`TransformFromCopy` from the arrows into the symbols).
5. **Solve** (the longest beat, 1 beat per equation): one algebra step per animation. Keep the same equation in place and transform it (`TransformMatchingTex`), so the student follows the algebra. Substitute numbers by moving them out of the diagram labels into the equation. Colour-match symbols to the quantities in the picture.
6. **Answer** (3 to 5 s): box the result (`SurroundingRectangle`), with units, in the result colour. Show the number on the picture again (the net force arrow, the landing point, the angle).
7. **Check / insight** (3 to 6 s, optional but encouraged): the sanity check, or a `ValueTracker` sweep that varies one parameter ("what if the angle grows?") so the teacher can discuss the trend.

A whole problem is 60 to 180 s. If it has several parts (a, b, c) use one scene class per part, sharing helpers, or one class with a `next_section` per part. Never cram more than one new idea per beat.

## Teacher features (make it classroom-ready)
- Every `next_section(name, notes=...)` carries the teacher's speaking note in `notes` (what to say and the common student mistake to watch for). Sections are the pause points: tell the user they can present with `manimgx` sections or render and pause there.
- Pause with `self.wait(...)` of 2 to 3 s before revealing each result so the teacher can ask "what do you think comes next?". For key moments add a visible "Predict" prompt: a small `Text("Predict: which way does it accelerate?")`, wait 3 s, then reveal.
- Show **common mistake** callouts only when real (wrong sign of friction, using `cos` for `sin`): red chip, one line, shown after the right method.
- Keep one running "Given / Find" panel in a corner (small, `GREY_B`) so late beats still show what is known.
- Use `self.say(...)` narration only if the user asks for voice-over.

## Reply format for this mode
1. **Problem as I read it**: Given / Find / Assumptions (short list).
2. **Solution in one glance**: the numbered steps with the final answer and units (3 to 8 lines).
3. **The complete scene file** (one code block, runnable).
4. How to run it (`manimgx inspect file.py Scene`, then render) and one to three tweak suggestions.
Flag anything you assumed or could not read from the image.
