# Explain a theory topic (concept in, classroom lesson out)

Use this when the user asks to explain, teach or animate a THEORY topic: quantum mechanics, classical mechanics, statistical mechanics, thermodynamics, electromagnetism, waves and optics, relativity, or a mathematics topic (linear algebra, calculus, Fourier, probability, complex analysis, ...). The product is understanding that survives an exam: the student can see it, say it, derive it, and write it for marks. Worked example (read it first): `theory_particle_in_a_box_manimo.py` in the workspace root (three scene classes: idea and maths, pictures and exam, a 3D part).

Problem mode has one right answer to reach; theory mode has one idea to make unforgettable. The same rules of precision, narration and checking apply.

## Stage 1: Scope the lesson (before any code)
Write down, in the reply's plan:
- **Audience**: class 12, first-year, second or third year, postgraduate. If the user does not say, assume first or second year and say so. The level fixes the maths (no operators for class 12; operators and Dirac notation only for later years).
- **The one idea**: finish the sentence "After this lesson the student can ___". One idea per lesson. A big topic becomes a series of parts (one scene class each, sharing helpers), each 4 to 8 minutes, with the order stated in the docstring.
- **Prerequisites**: list them. Recap in one beat only what the lesson really needs; assume the rest and say what is assumed.
- **Exam angle**: which questions this topic produces (state, derive, explain, sketch, numerical) and what each is worth. Ask only if the board changes the content.
- **Out of scope**: one line, so the lesson does not sprawl.

## Stage 2: Content audit (accuracy comes before animation)
Write the content on paper first and check it; never animate something unverified.
1. **Statements**: every definition and law in the textbook wording a student would be marked on, with its domain of validity (non-relativistic, ideal gas, small angles, equilibrium).
2. **Equations**: every symbol defined, with units or dimensions. Check each equation by **dimensional analysis**, a **limit** (classical limit, T to 0, large n, v much less than c) and, where possible, a **numerical check in Python** (normalisation integrals, sum rules, a known value). Put these checks as `assert` lines in the scene file so the animation cannot disagree with the physics.
3. **Derivation**: the shortest honest route, with the reason for each step ("because the wall is infinite", "by the chain rule"). Mark which steps are routine algebra (can be sped up) and which carry the physics (slow down).
4. **Analogies**: allowed only as a bridge. Say on screen or aloud where the analogy breaks ("this is only an analogy: the electron is not a tiny ball"). Never leave a wrong picture as the last image of a beat.
5. **Honesty**: if something is a convention, a model, an approximation or an open question, say which. If you are unsure of a fact, say so in the reply instead of guessing.

## Stage 3: The narrative arc (beats, in this order, adapt to the topic)
1. **Hook** (10 to 25 s): a puzzle, a surprising picture or a question the old idea cannot answer (a marble versus an electron; why does a cold gas not just stop). Let students predict.
2. **Intuition first**: one concrete picture or case with real numbers before any general law. Show, then name.
3. **Set-up**: the objects, symbols, assumptions. The picture appears first; its label second.
4. **The law**: built from the picture, piece by piece (`reveal-and-sync.md`), never pasted.
5. **Derivation** (when exams ask to derive): one step per beat; keep the equation in place and transform it (`TransformMatchingTex`); the voice says why, not only what; highlight the terms that change.
6. **Visual exploration**: make the formula move. A `ValueTracker` sweep (vary n, T, k, the mass) with the quantity that matters on screen, and the one thing that does NOT change pointed out.
7. **Limits and special cases**: classical limit, extreme values, symmetry. This is where students see the law is sensible, and where examiners ask "comment on".
8. **Worked mini-example** with numbers and units (the bridge to problem mode): given, find, formula, substitution, arithmetic, boxed answer to 3 s.f.
9. **Exam view**: the model answer as it would be written, one line per mark (see `theory-exam-and-mistakes.md`).
10. **Silly mistakes**: 4 to 6 cards, wrong then right (same file).
11. **Recap**: three takeaways, one per sentence, and an optional "check yourself" question with a pause.
A lesson part is 4 to 8 minutes. Never more than one new idea per beat.

## Stage 4: Representations (every idea in at least three forms)
Picture, equation, graph, number, words, analogy. Move between them deliberately: draw the picture, read the graph off it, write the equation from the graph, put a number in. Use `references/theory-visuals.md` for the idioms (and 3D), and `references/theory-playbooks.md` for the topic's usual pictures, key equations and traps.
- One colour per idea for the whole lesson; list the colours in a table at the top of the file (for example psi = BLUE_C, probability = YELLOW, energy = GREEN, nodes = ORANGE, mistakes = RED_C).
- Depth only when it carries meaning (3D rule in `theory-visuals.md`); otherwise stay 2D, which the layout checker can verify.

## Stage 5: Narration for theory (rich, but precise)
Everything in `reveal-and-sync.md` applies (equations piece by piece, fractions numerator first, lists one item per sentence, highlight the figure while speaking). In addition:
- **Say the meaning before the symbols.** "The energy is the sum of kinetic and potential" then show T + V. Do not read an equation aloud as a string of letters when the idea fits in a sentence; read it piece by piece when the order of the pieces is the idea.
- **Say why.** Each step has a reason in the sentence ("so psi is zero outside, because the wall is infinite").
- **Questions before reveals.** "What do you expect for the third level?" then a pause, then the answer.
- **Define each term the first time**, in plain words, then use it consistently. Name objects the way the textbook does.
- **Spoken maths**: write numbers, units, greek letters and operators the way they are said ("h-bar squared over two m", "psi double-prime", "the integral from zero to L", "n squared"). Spell out "kilonewtons", "electron-volts". Avoid characters TTS reads badly (no symbols like hbar, use "h-bar").
- **Rhythm**: sentences under about 70 characters or one idea; short sentence after a long one; a beat of silence (`self.wait(0.5)`) after a key reveal.
- **Flag the status of a statement**: "this is a law", "this is a definition", "this is an approximation", "this is a convention".

## Stage 6: Build it
- Same structure as problem scenes: docstring (the one idea and the parts), palette constants, a numbers section computed once with asserts, helper functions, a base mixin that is NOT a Scene (so the app lists only the real scenes), one class per part, one `next_section` per beat with the teacher's note in `notes=`.
- Pieces and spoken pieces must match one to one (the helper asserts it).
- Compute every plotted function and every number from the same formulas that are written on screen.
- No files, network or subprocesses. Randomness only with a fixed seed.
- Check with `manimgx inspect`. For a 3D scene the layout check is skipped ("not checked"), so look at the storyboard frames yourself and keep the text fixed in the frame, away from the surface.

## Teacher features
- `notes=` in every section: what to say, what to ask, the mistake to watch for.
- A "Predict" pause before key results; a "check yourself" question at the end.
- Mark clearly what is exam core and what is "going further" (put extensions in their own part).
- Say in the reply where the natural pause points are (the sections).

## Reply format for this mode
1. **Plan**: the audience, the one idea, the parts (one line each), the prerequisites assumed.
2. **Content in one glance**: the key definitions and equations (with units), the derivation outline, and the exam points, so the teacher can check the physics before running anything.
3. **The complete scene file(s)** (one code block per file; for several parts, say which class is which).
4. **How to run it** (each class), what was verified (inspect, asserts) and what was not (voice not heard, 3D checked by eye), and one to three tweaks.
Flag any simplification, convention or assumption you made.

## Checklist before you answer
- [ ] One idea per lesson; the docstring says it and lists the parts.
- [ ] Every equation checked: dimensions, a limit, a numerical assert where possible; domain of validity stated.
- [ ] Hook, intuition, law, derivation or explanation, visual exploration, limits, worked number, exam view, mistakes, recap all present (or consciously skipped).
- [ ] Every symbol defined before use; every number with a unit.
- [ ] Each idea in at least three representations.
- [ ] Equations revealed piece by piece in step with the words; the figure highlights what is spoken.
- [ ] Analogies flagged; no wrong picture left as a final image.
- [ ] A model answer with marks, and 4 to 6 mistake cards (wrong then right).
- [ ] Spoken text is written for the ear; spans equal animations.
- [ ] `manimgx inspect` clean for 2D; 3D scenes looked at by eye.
