"""Binary search: each guess throws away half of what is left.

One idea: halving a sorted list again and again finds anything in a handful of steps.
Beats: 1) a sorted row of numbers  2) check the middle, discard a half, repeat  3) the target is found.
"""

import manimgx as m

C_BOX = m.BLUE_C
C_DIM = m.GREY_D
C_PROBE = m.YELLOW
C_FOUND = m.GREEN_C

NUMBERS = [2, 5, 8, 12, 16, 23, 38, 42, 56, 72, 91]
TARGET = 23


def make_row() -> m.VGroup:
    cells = m.VGroup()
    for n in NUMBERS:
        box = m.RoundedRectangle(width=0.95, height=0.95, corner_radius=0.12, color=C_BOX, stroke_width=3)
        label = m.Text(str(n), font_size=30).move_to(box)
        cells.add(m.VGroup(box, label))
    return cells.arrange(m.RIGHT, buff=0.12)


def dim(cell: m.VGroup) -> m.AnimationGroup:
    return m.AnimationGroup(cell[0].animate.set_color(C_DIM), cell[1].animate.set_opacity(0.3))


class BinarySearch(m.Scene):
    def construct(self) -> None:
        title = m.Text("Finding 23 by halving", font_size=38).to_edge(m.UP, buff=0.35)
        self.play(m.FadeIn(title, shift=m.DOWN * 0.2))

        # ---- beat 1: the sorted row
        self.next_section("Row", notes="A sorted list. We want the position of 23.")
        row = make_row()
        row.scale_to_fit_width(12.4).move_to(m.ORIGIN)
        self.play(m.LaggedStart(*[m.FadeIn(c, shift=m.UP * 0.2) for c in row], lag_ratio=0.08), run_time=2)
        note = m.Text("sorted from small to large", font_size=26, color=m.GREY_B).next_to(row, m.DOWN, buff=0.5)
        self.play(m.FadeIn(note))
        self.wait(1)

        # ---- beat 2: look in the middle, discard half
        self.next_section("Halving", notes="Check the middle. 23 is smaller, so the right half goes.")
        lo, hi = 0, len(NUMBERS) - 1
        pointer = m.Triangle(color=C_PROBE, fill_color=C_PROBE, fill_opacity=1).scale(0.16).rotate(m.PI)
        counter = m.Text("guesses: 0", font_size=28, color=C_PROBE).to_edge(m.DOWN, buff=0.6)
        self.play(m.FadeOut(note), m.FadeIn(counter))
        guesses = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            guesses += 1
            target_pos = row[mid].get_top() + m.UP * 0.3
            if guesses == 1:
                pointer.move_to(target_pos)
                self.play(m.FadeIn(pointer))
            else:
                self.play(pointer.animate.move_to(target_pos), run_time=0.8)
            self.play(row[mid][0].animate.set_color(C_PROBE), run_time=0.4)
            new_counter = m.Text(f"guesses: {guesses}", font_size=28, color=C_PROBE).to_edge(m.DOWN, buff=0.6)
            self.play(m.Transform(counter, new_counter), run_time=0.4)
            if NUMBERS[mid] == TARGET:
                break
            if NUMBERS[mid] < TARGET:
                self.play(*[dim(row[i]) for i in range(lo, mid + 1)], run_time=0.8)
                lo = mid + 1
            else:
                self.play(*[dim(row[i]) for i in range(mid, hi + 1)], run_time=0.8)
                hi = mid - 1
            self.wait(0.4)

        # ---- beat 3: found
        self.next_section("Found", notes="Found it in just a few guesses.")
        self.play(row[mid][0].animate.set_color(C_FOUND), m.Indicate(row[mid], color=C_FOUND))
        done = m.Text("Found it. A million items would need only about 20 guesses.", font_size=28, color=C_FOUND)
        done.scale_to_fit_width(min(done.width, 12.0)).next_to(row, m.DOWN, buff=0.9)
        self.play(m.FadeIn(done, shift=m.UP * 0.2))
        self.wait(2)
