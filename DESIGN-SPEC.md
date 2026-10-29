# ManimGX Studio: product and design specification

Mode: **Operate** (the visitor completes a task). Brand lives in precise details, not decoration.

## 1. Vision and design principles

ManimGX Studio turns ManimGX animation code into a video in three moves: **add code, check the settings, press Start Rendering.** It should feel like a calm, trustworthy instrument: Linear's restraint, Raycast's speed, a code editor's precision.

1. **One obvious next step.** The primary button is always the single saturated element. A line beside it says what will happen ("Ready to render HelloManimGX") or what is missing.
2. **Progressive disclosure.** Quality, frame rate, engine and folder live in a settings popover. Render logs hide behind "Show details". Defaults are right for most people.
3. **Floating, not blocking.** Settings and progress are pop-outs over the editor. Nothing modal. Rendering never traps the user; the panel minimises to a pill.
4. **Honest feedback.** Progress is labelled as an estimate (ManimGX reports only when a video finishes) and learns from earlier renders of the same scene; the time left says "Estimating…" until it can be trusted. Errors name the problem and the recovery.
5. **Light and dark are equals.** Both are designed from the same tokens: warm paper and midnight ink, not an inverted afterthought.
6. **Depth only where it clarifies.** Blur and shadow appear on the two floating panels so they separate from code behind them. Everything else is flat and bordered.

## 2. Information architecture and flows

One screen, three layers.

```
Top bar      brand · file name · engine status · Open file · Settings · Theme
Workspace    code editor (empty state: Paste / Open / Example)
Run bar      output folder · Open folder · quality summary · hint · Start Rendering
Floating     Settings popover · Progress pop-out · Minimised pill · Toasts
```

**Flow: paste / load → configure → render → done**

| Stage | User does | System does |
|---|---|---|
| Add code | Paste, Open .py, drag a file onto the window, or Try an example | Highlights syntax, lists detected scenes, lets you pick which scene to render, warns about a missing `Scene` class |
| Configure (optional) | Taps the quality chip or the sliders icon | Opens settings: quality, frame rate, video encoding, folder, appearance. Choices persist |
| Render | Start Rendering (or Ctrl+Enter) | Closes settings, opens the progress panel, runs ManimGX, shows estimated percent, elapsed time and ETA |
| Done | Play video, Open folder, Render again | Moves the finished video into the chosen folder, cleans temp files |
| Problem | Reads the plain-language cause, Try again, or Copy details | Maps the common errors (syntax, missing import, several scenes) to a one-line explanation |
| Cancel | Cancel render, then confirms inline | Kills the whole ManimGX process tree; saves nothing |

## 3. Visual design system

**Colour** (OKLCH, defined as CSS custom properties; accent is the only saturated hue, green and red appear only for outcomes).

| Token | Light (paper) | Dark (midnight) |
|---|---|---|
| `--bg` | `oklch(0.972 0.006 85)` | `oklch(0.165 0.022 265)` |
| `--surface` | `oklch(0.995 0.003 85)` | `oklch(0.20 0.024 265)` |
| `--surface-2` | `oklch(0.952 0.007 85)` | `oklch(0.245 0.026 265)` |
| `--line` | `oklch(0.905 0.008 85)` | `oklch(0.30 0.026 265)` |
| `--text` / `-2` / `-3` | `0.21` / `0.43` / `0.52` L, hue 265 | `0.955` / `0.78` / `0.67` L, hue 265 |
| `--accent` | `oklch(0.52 0.19 262)` | `oklch(0.72 0.15 258)` |
| `--ok` / `--danger` / `--warn` | green 155 / red 27 / amber 70 | lighter equivalents |
| Syntax | keyword 305°, string 155°, number 55°, class 245°, function 205° | same hues, lifted lightness |

Body and placeholder text meet 4.5:1; large text 3:1.

**Type.** System stacks only, so it works offline and feels native: UI `system-ui` (Segoe UI Variable on Windows); code `Cascadia Code → ui-monospace → Consolas`. Scale 12.5 / 13.5 / 14 / 15 / 18 / 28 / 44 px. Weights 400, 500, 600, 650. Tabular numerals on every number that changes. Headings use `text-wrap: balance`, tracking −0.01 to −0.03em.

**Spacing** 4 · 8 · 12 · 16 · 24 · 32 · 48. **Radius** 6 (inner) · 10 (controls) · 14 (cards) · 20 (floating panels) · 999 (pills).

**Elevation.** `--sh-1` for resting cards (1px + 1px). `--sh-pop` for floating panels (three layers: contact, mid, ambient), tinted to the palette hue. Backdrop blur 22px only on floating panels, with a solid fallback.

**Icons.** Authored SVG sprite, 24px grid, 1.75 stroke, round caps and joins, `currentColor`. No emoji.

**Motion.** One authored moment: panels arrive with a 380ms exponential ease-out (rise 14px, scale .96→1, blur 6→0) and leave in 200ms. Everything else is a 150–250ms state change. The progress bar is a `scaleX` transform with a slow sheen while running. The completion tick draws itself. `prefers-reduced-motion` removes all of it.

## 4. Desktop layout

- **Top bar (56px).** Brand mark + wordmark, file chip, spacer, engine status pill, Open file, Settings, Theme.
- **Workspace.** Editor card, max 1240px, centred. Header (file name, Paste / Example / Clear), gutter + highlighted code, footer (scene summary left, cursor position right). Empty state sits over the code area with the three entry points.
- **Run bar.** Output folder chip, Open-folder button, quality summary chip, a hint line, and the Start Rendering button on the far right at 48px tall.
- **Settings popover.** Anchored under the top bar, 380px, right-aligned.
- **Progress pop-out.** Bottom-right above the run bar, 380px: status dot, percent (44px), scene name, bar, 2×2 stats (Elapsed, Time left, Resolution, Frame rate), Cancel, and a "Show details" log.

## 5. Mobile and responsive behaviour

| Width | Change |
|---|---|
| ≤1000px (tablet) | Hint line hides; chips share the row; side padding 16px |
| ≤720px (phone) | Top bar keeps brand, status dot, open, settings, theme. Editor uses 16px code (stops iOS zoom) and fills the screen. Run bar becomes two rows: folder + quality chips, then a full-width 52px Start button with the hint above it. Settings and progress become **bottom sheets** with a grab handle, safe-area padding and (for settings) a scrim. Minimised progress pill spans the width. All touch targets ≥44px |

Uses `100dvh`, `env(safe-area-inset-*)`, and `viewport-fit=cover`.

## 6. Interactive states and micro-interactions

- **Start button.** Rest · hover · pressed (1px down) · focus ring · "needs input" (dimmed, click explains) · running (`Rendering 42%`, click re-opens the panel).
- **Progress panel.** Preparing (percent 0, "Preparing scene…") → Rendering (live numbers, sheen on bar) → Done (green bar, drawn tick, file chip, Play video primary) / Error (cause, log, Try again, Copy details) / Stopped.
- **Cancel** swaps the button row for an inline "Stop this render? Keep going / Stop". No modal.
- **Minimise** collapses to a pill with a mini bar and percent; it re-expands on completion.
- **Window title** carries the percent, so the render is visible from the taskbar.
- **Toasts** for passive confirmations (loaded file, copied, folder changed).
- **Editor.** Tab indents, Enter keeps indentation (and adds a level after `:`), drag-and-drop a `.py` anywhere.
- **Theme toggle** cross-fades colours in 250ms and persists. "System" follows the OS live.

## 7. Component breakdown

`AppShell` · `TopBar` · `Brand` · `FileChip` · `EngineStatusPill` · `IconButton` · `Button (primary / secondary / ghost / danger)` · `CodeEditor` (`Gutter`, `HighlightLayer`, `Textarea`, `EmptyState`, `EditorFooter`) · `RunBar` (`FolderChip`, `SettingsChip`, `StartButton`, `HintLine`) · `FloatingPanel` (popover on desktop, `BottomSheet` on phone) · `SettingsPanel` (`SegmentedControl`, `OptionCard`, `PathRow`) · `ProgressPanel` (`BigPercent`, `ProgressBar`, `StatGrid`, `InlineConfirm`, `LogDisclosure`, `ResultView`) · `MiniPill` · `Toast` · `DropOverlay`.

## 8. Accessibility

- Every control is a real `button`, `input` or `textarea`; the editor is a native textarea under a decorative highlight layer, so selection, IME, undo and screen readers behave.
- Visible 2px focus ring on everything; Escape closes settings or minimises progress; arrow keys move within segmented controls (`role=radiogroup`).
- The progress bar is `role=progressbar` with `aria-valuenow`; a polite live region announces start, each 25%, completion and failure, so it is not chatty.
- Colour never carries meaning alone: status pills pair a dot with text; errors pair an icon with a sentence.
- Contrast ≥4.5:1 for body text in both themes; touch targets ≥44px on phones; text scales with the browser; reduced-motion respected.
- Plain language throughout. "Processor" and "Graphics card" instead of "Cairo" and "OpenGL" as the main label, with the technical name in brackets.

## 9. Tech stack

| Layer | Used in this build | Recommended next |
|---|---|---|
| UI | One HTML file, vanilla JS, CSS tokens, no network access needed | React + TypeScript + Tailwind; Framer Motion for the panel choreography; CodeMirror 6 for a full editor |
| Desktop shell | Local Python server + Edge/Chrome `--app` window | Tauri 2 (small, native window, auto-update) wrapping the same server as a sidecar |
| Render engine | `python -m manimgx render` in a private venv (GPU core); progress estimated from earlier render times | Keep; add scene picker and cached previews |
| Installer | PowerShell + WinForms, venv, shortcuts | Inno Setup `.exe` that embeds the same logic and is code-signed |
| Safety | 127.0.0.1 only, per-launch token, Host-header check, no CORS | Same |
