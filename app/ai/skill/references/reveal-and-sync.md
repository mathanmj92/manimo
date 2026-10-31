# Reveal and sync: show what is said, when it is said (3Blue1Brown level)

Rules learned from classroom feedback. They apply to every scene with narration, and most of all to worked solutions.

## The rules
1. **One equation line = one sentence group.** Never write a bullet list, a block of equations, or a long line in one go while the narration is reading its first item. Each line is built and spoken on its own.
2. **Reveal an equation piece by piece, left to right, in step with the words.** A piece is a term or a small group (`R_x=`, `-2.376`, `+3.906`, `=1.530`). Say the words of a piece while exactly that piece is written. The listener should never see a symbol before it is spoken, or hear a number that is not yet on screen.
3. **Fractions: numerator first, then the bar and the denominator.** Reveal the numerator terms one by one (the bar is drawn with the first one), say "over", then reveal the denominator. Never show a finished fraction.
4. **Radicals, sums and integrals reveal left to right too.** For an integral: the sign with its limits first, then the integrand piece by piece, then `dx`, then `=` and the result. For a radical, write it over the span in which its contents are spoken (the Write animation runs left to right while the words go by).
5. **No bare operators as pieces.** Join `=`, `+` and `-` to the neighbouring term (`F_{AB}=` then `4.2`, `+3.906`, `=1.530`). A lone `=` glyph is tiny and the layout checker reports it as an 11 px label.
6. **Highlight the part of the picture being worked on.** Every piece may carry an extra animation that points at the figure: flash an edge, indicate the cable, grow the arrow, fill the right triangle and draw its arc. Trigonometry always shows the triangle and the angle in the figure; component sums show the legs of the box; a length shows the box diagonal; a unit vector shows the unit arrow, which then stretches into the force.
7. **Lists appear one item per sentence.** Traps, steps, model-answer lines: each is written while its own sentence is spoken.
8. **Clear the panel before building the next one.** Register every panel item, and create the wipe animation at the start of a beat (before the new lines are created) so it does not remove them.
9. **Keep the words and the pieces locked.** The helper asserts that the number of reveals equals the number of spoken pieces. If it fails, fix the script, never the assert.
10. **Colour carries meaning across picture and algebra** (for example x, y, z components in the same colours as their edges and terms).

## Helpers (tested; paste into the scene file)
```python
def tex_piece(piece, size, color):
    if isinstance(piece, tuple):
        return m.MathTex(piece[0], font_size=size, color=piece[1])
    return m.MathTex(piece, font_size=size, color=color)


def build_eq(pieces, size=34, color=m.WHITE, gap=0.14):
    """pieces: 'tex' | ('tex', colour) | ('frac', [numerator pieces], [denominator pieces]).
    Returns the (invisible) group laid out left to right and ONE reveal animation per spoken piece;
    a fraction gives its numerator pieces first (the first together with the bar), then its denominator pieces."""
    mobs, reveals = [], []
    for piece in pieces:
        if isinstance(piece, tuple) and piece[0] == "frac":
            num = m.VGroup(*[tex_piece(p, size, color) for p in piece[1]]).arrange(m.RIGHT, buff=gap * 0.8)
            den = m.VGroup(*[tex_piece(p, size, color) for p in piece[2]]).arrange(m.RIGHT, buff=gap * 0.8)
            width = max(num.width, den.width) + 0.2
            num.move_to([0.0, num.height / 2 + 0.12, 0.0])
            den.move_to([0.0, -den.height / 2 - 0.12, 0.0])
            bar = m.Line([-width / 2, 0.0, 0.0], [width / 2, 0.0, 0.0], color=color, stroke_width=3)
            mobs.append(m.VGroup(num, bar, den))
            for k, part in enumerate(num):
                reveals.append(m.AnimationGroup(m.Write(part), m.Create(bar)) if k == 0 else m.Write(part))
            reveals.extend(m.Write(part) for part in den)
        else:
            mob = tex_piece(piece, size, color)
            mobs.append(mob)
            reveals.append(m.Write(mob))
    return m.VGroup(*mobs).arrange(m.RIGHT, buff=gap), reveals


def seq(reveals, texts):
    """Pair each reveal with the words spoken while it appears: 'words' or ('words', extra animation(s) for the figure)."""
    assert len(reveals) == len(texts), f"{len(reveals)} reveals but {len(texts)} spoken pieces"
    parts = []
    for reveal, text in zip(reveals, texts):
        if isinstance(text, str):
            parts.append((text, reveal))
        else:
            words, extra = text
            extras = [] if extra is None else (list(extra) if isinstance(extra, (list, tuple)) else [extra])
            parts.append((words, m.AnimationGroup(reveal, *extras) if extras else reveal))
    return parts
```
and in the scene class:
```python
def talk(self, *parts):        # a part is plain words, or (words, animation): the animation plays while those words are said
    script, animations = [], []
    for part in parts:
        if isinstance(part, str):
            script.append(part)
        else:
            script.append(f"[{part[0]}]")
            animations.append(part[1])
    self.say(" ".join(script), *animations)

def line(self, pieces, y, texts, size=34, color=m.WHITE, left=PANEL_LEFT):   # build one equation line, remember it for wipe()
    group, reveals = build_eq(pieces, size, color)
    panel(group, y, left)
    self.shown.append(group)
    return group, seq(reveals, texts)

def wipe(self):                # FadeOut of everything shown so far; create it at the START of a beat
    items, self.shown = self.shown, []
    return m.AnimationGroup(*[m.FadeOut(i) for i in items]) if items else m.Wait(0.01)
```
Usage:
```python
eq, parts = self.line([("R_x=", C_X), "-2.376", "+3.906", "=1.530"], 1.65,
                      ["R x equals", "minus 2.376,", "plus 3.906,", ("which is 1.530.", Create(leg_x))])
self.talk("In x,", *parts)
```
A vector with coloured components: build pieces such as `("-4\\,\\hat{i}", C_X)`; a fraction: `("frac", [num pieces], [den pieces])`; an integral: `["\\int_{0}^{L}", "w(x)", "\\,dx", "=", ...]`.

## Testing without the voice
`self.say` needs the voice, so test with a silent stand-in (never part of the deliverable): subclass the scene in a scratch file with `voice = staticmethod(quiet_voice)`, where `quiet_voice(text)` returns `m.audio.Speech(samples, text=text, rate=24000)` of low-level noise lasting `len(text.split()) / 2.6` seconds, then `manimgx inspect`. It checks that every span has its animation, that nothing overlaps, and that no tiny label remains. Each `say` is one sample, so also read the storyboard frames to see the final state of every step.
