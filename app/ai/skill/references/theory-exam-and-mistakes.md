# Exam view and silly mistakes (theory topics)

Students lose marks on theory for habits, not for ignorance: a missing boundary condition, a lost factor, h for h-bar, "n starts at 0". Every theory lesson therefore ends with the exam view and a set of mistake cards. Worked example: `theory_particle_in_a_box_manimo.py` (the "Exam answer" and "Silly mistakes" beats of `BoxPicturesAndExam`).

## 1. Classify the question (and say so)
| Question type | What earns the marks | Beat to show |
|---|---|---|
| **State / define** (1 to 3 marks) | The exact wording, symbols named, units, validity condition | The definition in a box, key words coloured; "write exactly this" |
| **Derive / prove** (5 to 8 marks) | Starting point, each step with its reason, the boundary or initial conditions, the boxed result | Marked model answer, one line per mark |
| **Explain / discuss** (3 to 5 marks) | A cause-and-effect chain in physical words, then the formula as support | Three-line chain: cause, mechanism, consequence |
| **Sketch** (2 to 3 marks) | Labelled axes with units, intercepts, nodes, asymptotes, the right shape and relative heights | The sketch drawn step by step, then the checklist of labels |
| **Numerical** (3 to 5 marks) | Formula, substitution, arithmetic, unit conversion, 3 s.f., unit on the answer | Worked mini-example, three lines per formula |
| **Compare / contrast** | Same, different, and why | Two side-by-side pictures with the difference highlighted |
| **Limiting case / comment** | The limit taken, the result, its meaning | The classical or extreme-value beat |

## 2. The marked model answer (the key beat)
- Header: "Write this in the exam (N marks)". One line per mark, each tagged `[1]` in grey at the left, the equation at the right, and one spoken sentence saying what that line earns ("apply the two boundary conditions").
- Reveal one line per sentence, never the whole page at once. The last line says: define every symbol, give units, state the range of n.
- The lines are exactly what a student can reproduce in a few minutes: no decoration, no extra proofs.
- State the assumptions the examiner expects (ideal gas, non-relativistic, rigid walls, small angles).
- Box the final result in the answer colour, with units and conditions (for example `n = 1, 2, 3, ...`).

## 3. Answer-writing habits to teach (say them, show them)
1. Start with the principle by name ("Schrodinger equation inside the box", "first law of thermodynamics").
2. Define every symbol the first time; write units on every numerical line.
3. State the conditions (boundary, initial, validity) before using them.
4. One step per line; give the reason in words when a step is not plain algebra.
5. Draw the sketch with labels; mark the quantity asked.
6. Box the result; add a one-line sanity check (units, limit, sign, order of magnitude).
7. Use the symbols of the question, not your own.

## 4. Self-checks to show on screen (they catch most errors)
- **Dimensions**: show the units of both sides of the key equation.
- **Limits**: put in the extreme value (n large, T to 0, v much less than c, damping to 0) and read the result.
- **Facts a student can verify**: probabilities add to 1, the first level is the lowest, entropy of an isolated system does not decrease.
- **Order of magnitude**: an electron in a nanometre box has energies of electron-volts, not millijoules.

## 5. Mistake cards: how to build and show them
Per topic choose 4 to 6 real mistakes (see the catalogue in `theory-playbooks.md`). Each card has:
1. **Name** in red, one line ("Starting at n = 0").
2. **Wrong version** in red (equation, sentence or picture), shown briefly.
3. **Right version** in green, shown piece by piece; this is the last image of the card.
4. **Why it is wrong and why students do it**, in the voice (one or two sentences), with the quick test that exposes it ("n equals zero gives psi equal to zero: no particle").
Rules: never leave the wrong version as the final image; keep wrong versions off the model-answer page; ask "which of these have you made?" in `notes=`; finish with a three-line recap of the takeaways.

## 6. Kinds of mistake to look for in any topic
- **Boundary and initial conditions**: forgotten, or applied to the wrong quantity.
- **Index and range**: n from 0 or 1; wrong limits on a sum or integral; degeneracy counted once.
- **Factors**: 2, pi, 1/2, 4 pi r squared; h versus h-bar (hbar = h / 2 pi); k_B and R mixed; molecules and moles.
- **Powers**: E proportional to n squared (box) but to n + 1/2 (oscillator); v versus v squared.
- **Units and conversions**: joules and electron-volts; Celsius and kelvin in a ratio; degrees and radians on a calculator.
- **Signs**: work done by versus on the gas; zero of potential energy; the sign of a negative cosine.
- **Confusing objects**: amplitude versus probability; heat versus temperature; mass versus weight; microstate versus macrostate; speed versus velocity.
- **Pictures that mislead**: orbits for electrons; "entropy is only disorder"; field lines as paths; "centrifugal force is real".
- **Conditions ignored**: a formula used outside its domain (non-relativistic, ideal, equilibrium).
- **Normalisation and constants**: forgetting the factor that makes the total probability one.

## 7. End with practice
An optional "Check yourself" beat: three short questions (one numerical, one "what happens if", one "what is wrong with this line"), each with a visible pause of about 5 s, then the answer.
