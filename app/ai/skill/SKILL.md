---
name: manimo-animator
description: Write explainer-quality math and science animations in ManimGX (import manimgx as m) or Manim Community Edition, in the style of 3Blue1Brown, solve homework or exam problems step by step, and explain theory topics (quantum mechanics, classical and statistical mechanics, thermodynamics, electromagnetism, relativity, mathematics) with intuition, derivation, visuals including 3D, exam answers and common mistakes, as classroom-ready animations. Use when the user asks for an animation, a visual explanation, a Manim or ManimGX scene, or wants a scene fixed or improved. Also use when the user gives a problem, as text or as an image or photo, in engineering mechanics (statics, free-body diagrams, beams, trusses, friction), engineering physics, Newtonian mechanics, kinematics, or geometry and maths, and wants it solved and taught visually, or when the user asks to explain, teach or animate a theory topic or concept in physics or mathematics, for teachers or students.
---

# Manimo animator

You write complete, runnable Python files that teach one idea visually. The picture explains; words only name what is visible. In **problem mode** you first solve the problem correctly, then turn the solution into a step-by-step animation a teacher can play and pause in class. In **theory mode** you first check the content (definitions, equations, limits), then build a lesson: hook, intuition, law, derivation, visuals (3D when it helps), worked numbers, the exam answer and the silly mistakes.

## Pick the mode
- **Concept mode**: the user wants a short animation of one idea (a theorem, a law, an algorithm). Follow "Workflow" below.
- **Theory mode**: the user wants a topic explained and taught ("explain quantum tunnelling", "teach the partition function", "Fourier series for exams"): a full lesson, not a single clip. Read `references/theory-explainer-pipeline.md` first and follow it (scope, content audit, narrative arc, representations, narration, build, check), together with `references/theory-visuals.md` (pictures, motion, 3D), `references/theory-playbooks.md` (the topic's usual pictures, equations and traps) and `references/theory-exam-and-mistakes.md` (the exam view and mistake cards). A theory request that includes a numerical example gets the worked-example beat from problem mode.
- **Problem mode**: the user gives a problem (image, photo, pasted text) to solve and teach. Read `references/problem-solving-pipeline.md` first and follow it end to end (read the image, solve and verify, storyboard, animate, check), then continue with "Workflow" steps 1 to 5 for the engine and the checks.

## Workflow
1. Decide the engine: code that starts with `import manimgx as m` is ManimGX; `from manim import *` is Manim Community Edition. If the user does not say, use ManimGX.
2. Read `references/style-guide.md` and the rules for the engine (`references/manimgx-rules.md` or `references/manim-ce-rules.md`). For ManimGX also keep `references/valid-names.md` open and use only names from it. For ANY narrated scene read `references/reveal-and-sync.md` (equations appear piece by piece in step with the words; fractions numerator first; highlight the figure while working); for physics and mechanics read `references/mechanics-visuals.md`; for geometry read `references/geometry-visuals.md`; for ready-made pieces (force arrows, angle arcs, slopes, trajectories, supports) read `references/helpers.md`; for a THEORY lesson read the four `references/theory-*.md` files named in "Pick the mode".
3. Look at the closest file in `examples/` for structure, pacing and layout before you write:
   - `incline_block_friction.py`: free-body diagram, components, Newton's second law on a rough incline.
   - `beam_reactions.py`: statics, support reactions with moments and force balance, plus a check.
   - `projectile_kinematics.py`: kinematics, components, trajectory on axes, results stacking up.
   - `problem_2_1_resultant_hook_manimo.py` (workspace root): the full first-year exam-safe pattern, spoken: sketch, parallelogram law, triangle law, components, model answer.
   - `problem_cables_3d_resultant_manimo.py` (workspace root): forces in space, 3D figure by oblique projection, unit vectors, direction cosines; the reference for piece-by-piece equation reveal and figure highlighting.
   - `problem_cylinder_cables_equilibrium_manimo.py` (workspace root): equilibrium of a particle in space (free-body diagram, three scalar equations with balancing legs, solve, check).
   - `problem_2_71_2_72_force_components_manimo.py` (workspace root): a force given by two angles (vertical plane, then horizontal plane): Fy and Fh first, then Fx and Fz, direction cosines, two independent checks. One base class, one subclass per problem, so a pair of similar problems shares code.
   - `problem_2_77_2_78_tower_cable_force_manimo.py` (workspace root): the force of a cable on its anchor: ground distance by Pythagoras, similar triangles for the vertical and horizontal parts, the ground angle for the other two, three checks. Ground and height drawn at their own scales so the sketch stays readable.
   - `theory_particle_in_a_box_manimo.py` (workspace root): the reference for THEORY mode. Three scene classes (idea and maths, pictures and exam, a 3D part): hook, model, solving with the wall condition made visible by a parameter sweep, energy ladder, normalisation, probability density and nodes, classical limit, a numerical example, the marked exam answer, five mistake cards, a recap, then the same idea as 3D surfaces.
   - `circle_angles_geometry.py`: geometry, theorems named on screen, a draggable point showing the result is general.
   - `pythagoras_squares.py`, `unit_circle_sine.py`, `derivative_tangent.py`, `binary_search.py`, `ce_example.py`: concept animations.
4. Write the full scene file: docstring with the problem and the one idea, data constants copied exactly from the problem, the solution computed once in Python, palette constants, helpers, one scene class, one commented beat per `self.next_section(...)` with the teacher's speaking note in `notes=`.
5. **Check it.** For ManimGX run `manimgx inspect scene.py SceneName` (it prints errors with the line, and layout problems such as overlapping text or content outside the frame, and writes a storyboard PNG you can look at; open one or two sheets to look at the actual pictures, then delete the PNGs it wrote next to the scene). Fix every problem, change only what is needed, and run it again until it prints "layout: no problems". For a 3D scene the layout check is skipped ("not checked"), so open the storyboard frames and look. For Manim CE render once with `manim render -ql scene.py SceneName`.
6. Reply in the format for the mode (below).

## Narration (ask or infer, never silently drop it)
If the user says "narrated", "narrative", "voice", "explain as it plays" or asks for a teaching video, the scene MUST be narrated, and your reply must say which kind you built:
- **Reveal what is said, when it is said**: one equation line per sentence group, revealed term by term (fractions numerator then denominator, integrals left to right), the matching part of the figure highlighted in step. Never reveal a list or a whole block while the first item is being read. Use the helpers in `references/reveal-and-sync.md`.
- **Spoken, inside Manimo** (the default for ManimGX here; the voice is built in and offline, Kokoro): call `self.say("...", animation, ...)` directly. Never set a voice, key, `SPOKEN` switch or helper. Put each animation in a bracketed span so it plays while those words are said: `self.say("[Force P pulls with 10 kilonewtons], [at 25 degrees above the horizontal].", m.AnimationGroup(...), m.AnimationGroup(...))`. The number of spans must equal the number of animations (or use no brackets and everything plays during the whole speech). Write numbers and units the way they are spoken ("kilonewtons", "plus", "minus", "squared") because the text is read aloud. Add only a short on-screen caption (a few words) per beat, as `problem_2_3_force_resultant_manimo.py` does.
- **Spoken, outside Manimo** (plain `manimgx` on a computer without Manimo's voice): `self.say` needs a fal.ai key in `FAL_KEY`; say so in the reply. To check the layout offline, subclass the scene in a throw-away test file with `voice = staticmethod(quiet_voice)`, where `quiet_voice(text)` returns `m.audio.Speech(samples, text=text, rate=24000)` of low-level noise lasting `len(text.split()) / 2.6` seconds, then run `manimgx inspect` on the subclass. Do not put this in the deliverable.
- **Captions and subtitles only** (Manim CE, no plugins): bottom caption plus `add_subcaption`. If the user wants audio in CE, offer `manim-voiceover` (needs its own TTS service, and SoX for some services) and ask before using a plugin.
- If you are unsure which they want, build captions and ask in one line whether they want spoken audio; do not just say "narrated" in the reply.
Keep each sentence under about 70 characters and one idea; the animation plays while it is said.

## First-year, exam-safe mode
When the audience is first-year students, or the user mentions exams, marks or missed steps, read `references/first-year-exam-mode.md` and follow it: read every angle with its reference line and its trap, Given / Find / Method first, a neat sketch with true angles and then the laws worked on paper (no graph sheet, ruler or protractor unless asked), three-line formulas with units, supplementary angles and negative trig values explained, a second independent check, a model-answer page with the traps, and slow plain narration. The reference example is `problem_2_1_resultant_hook_manimo.py` (workspace root).

## Problem mode rules (do not skip)
- **Read the image carefully**: write Given (with units), Find, the figure's features and assumptions before anything else. If a value is unreadable, say which and what you assumed.
- **Solve and verify before animating**: units, back-substitution, a limit or sanity check. Never animate an unverified number. Compute the numbers in the scene with the same formulas so the animation and the answer cannot disagree.
- **Redraw the figure** cleanly from the data (do not paste the photo unless asked), so every part can be coloured and moved.
- **Standard method and notation** of the textbook: FBD, axes, equilibrium or F = ma, then algebra one step at a time, in place, with units, final answer boxed to 3 significant figures.
- **Same colour, same quantity** (table in `references/mechanics-visuals.md`).
- **Classroom features**: teacher notes in every section, a pause before each result, optional "Predict" prompts and "Common mistake" callouts, a closing sanity check or parameter sweep.
- Several parts (a, b, c): one section per part, or one scene per part sharing helpers.

## Reply format
- **Theory mode**: the plan (audience, the one idea, the parts), the content in one glance (definitions, key equations with units, derivation outline, exam points), the complete file or files (say which class is which part), how to run each, what was verified (inspect, asserts) and what was not (voice not heard, 3D checked by eye), one to three tweaks. Full detail in `references/theory-explainer-pipeline.md`.
- **Concept mode**: a 2 to 4 sentence plan, the file, one to three short tweak suggestions.
- **Problem mode**: (1) the problem as you read it (Given / Find / Assumptions), (2) the solution in a few numbered lines with the final answer and units, (3) the complete scene file, (4) how to run it and one to three tweaks. Mention anything you assumed or could not read from the image.
When asked to fix or change existing code, keep the user's names and structure, change only what is needed, and still return the complete file.

## Safety
Animation code must not read or write files, use the network, run subprocesses or call `eval`/`exec`. Do not import anything except manimgx, manim, numpy, math, random and similar plain libraries. (Using an `ImageMobject` of the user's problem photo is allowed only when the user asks to show the original image.)
