# Changelog

All notable changes to Manimo. Versions follow the installer (`installer/Manimo.iss`).

## 2.0.0
A big step: Manimo now takes a lesson from an idea to a printed handout. It includes everything from 1.10.0 and the new work below. There is no change to how existing code or projects are read.

- **Find any command (Ctrl+K).** Type a few words to find and run any menu command, layout or setting. Press `?` outside the editor for the keyboard shortcuts.
- **Plainer render errors.** The error card now names the thing that went wrong (for example "`Cirle` is not defined. Did you mean `Circle`?"), and has a **Fix with the assistant** button that sends the error and your code.
- **Version history** (Edit, Version history). Manimo keeps the last 30 versions of each file, saved after a pause in typing and before every render. See what changed, and restore one; the version you replace is kept too.
- **Problems beside the line numbers.** The code check's findings now also show as red and amber marks next to the line numbers, not only in its panel.
- **Storyboard** (the Code / Storyboard switch above the editor). One card per scene with its first frame, length, number of spoken words and animations, and a status (not rendered, rendering, rendered, changed since render, problems). Drag cards or use the arrows to reorder, duplicate, delete, rename, add a scene from five templates (title, equation, graph, side by side, summary), render one scene or all, or play a finished scene. Every change is a normal edit to your code, so Ctrl+Z undoes it; imports, helper functions and comments stay where they were.
- **Plan as cards.** On a plan from "Plan first", **Edit as cards** opens each planned scene as a card (name, what the viewer sees, narration) to change, reorder, add or delete. Then **Write one scene at a time** asks for each scene separately and checks it before the next, so a problem in scene 4 redoes scene 4, not the whole file. **Write all at once** is still there.
- **Narration studio** (the **Narration** button above the preview, which replaces Script). Every spoken line of the lesson is a row you can read, change and hear (with the offline voice, exactly as it will render), with its real length and a warning when a line is too long or much longer than the animation written for it (the animation would play slowly). Pick a voice and speed for the lesson, and a different voice or speed for any scene. Edits go straight into the quoted words in `self.say("...")`; the code around them is never touched, and each line keeps its `[bracketed]` parts. **Export the script** is still there.
- **Pronunciations.** Say a written word differently, only when it is spoken (`mu_k` as "mu k"). A built-in list also reads Greek letters, units, signs, `sin`, `cos` and `tan` aloud correctly, and can be turned off. They are saved as `# say:` lines at the top of the file, and per-scene voice and speed as `# voice:` and `# speed:` lines above the scene, so they travel with the lesson, survive reordering scenes, and are used when rendering.
- **Rewrite the narration with the assistant.** Make it shorter, simpler for a class level, or split long lines. Only the spoken words are sent (not your code), and a rewrite that loses a `[bracketed]` part is refused for that line.
- **Caption style** (the **Aa** button in Compose): size, position (bottom, middle, top), colour and an optional dark box, with a live preview on a frame of your first clip. The separate `.srt` file is still always saved next to the exported video.
- **Export lesson** (File menu, or the Storyboard). One place for four things:
  - **Lesson PDF**: a handout with the problem, its worked solution (Given, Find, Method, Steps, Answer, Check, filled in from the assistant's last solved problem or typed by you), the narration as numbered steps, and optionally a picture from the video for each spoken line (or a few per scene, or none). **Large pictures** run across the page so labels and arrows stay readable when printed (or choose Compact to save pages), **Large print** makes the type bigger, and pictures can have a light background for printing. The picture for each step is the latest moment where that step is complete (not a half-drawn or faded-out frame), and a step with no clear picture is reported. A figure from the first scene can sit beside the problem. Text colours are kept at readable contrast (a pale accent colour is darkened for text). "Made with Manimo" and the page number are in the footer of every page; there is no separate brand page. It is made with the Edge browser Windows already has (no new download); if Edge is missing it saves a web page to print instead.
  - **PowerPoint (.pptx)**: a title slide, the problem with its figure, the solution split over slides, then a slide for each spoken line with its picture (or one slide for each scene). The narration is in each slide's speaker notes, pictures have alt text, and every slide's footer says it was made with Manimo. Written without any extra library.
  - **GIF** of a rendered scene, for slides and chat.
  - **Share folder**: the ticked scenes joined into one video, a cover picture, the title, a description and chapter times.
  - **My brand**: your name or school, a line under it, an accent colour and a logo, shown at the top of your handouts.
- **My videos** can be searched and sorted (newest, oldest, name, largest), and selected videos moved to the Recycle Bin.
- **Prompt library**: search, filter by class level (school, class 11 and 12, college), favourites with a star, a "Used before" mark, and a **Request a prompt** button that opens a short GitHub form.
- **What each reply cost.** Every assistant reply shows its tokens (in and out), rounds and seconds. These are the counts the AI service reports (Anthropic API, Claude Code) or, for other services, an estimate of about four characters a token, marked "about". AI settings shows this month's total (requests, tokens, time). It is kept on this PC only.
- **Ask about one scene.** Each storyboard card has an **Ask the assistant…** menu: *Explain this scene*, *Make it easier*, *Make it harder*, *Make it shorter*. The assistant is shown only that scene and told to change nothing else.
- **Compare two takes.** The assistant writes a scene twice (once close to what you have, once in a clearly different way). You see the current scene and both takes side by side with their frames, length and problems, and keep the one you like. Only that scene is replaced (new imports are added), and Ctrl+Z undoes it. It asks the assistant twice, so it costs about twice one edit.
- **Past conversations** (the clock button in the assistant). Chats are saved on this PC after each reply, grouped by lesson. Search every message, pin the ones worth keeping, open an old one to carry on, or delete it. Unpinned conversations beyond 40 per lesson are cleared; pinned ones never are.
- **Quick start.** A three-step strip (get code, connect an AI, render) ticks itself as you go. Skip it any time; Help, Show the quick start brings it back.

## 1.10.0
- **Missing packages are found and can be installed.** The code check lists imports that Manimo's Python does not have (for example `scipy`, `sympy`, `cv2`) with an Install button for each, or Install all. It downloads from PyPI, wheels only so no package build script runs, and only after you press the button. A package that is not on Manimo's short list of known libraries asks for a second confirmation.
- **Plan first** (a switch under the assistant's message box). For a lesson or topic, the assistant first writes a short plan: a title, who it is for, the colours, and 3 to 8 scenes with their narration, about 200 tokens to send. Press "Looks good: write the scenes" to get the code, one scene class per planned scene, or "I will change it" to edit the plan first. Problems still use "Solve first". Ideas credited in the README.
- **Fix memory.** When the assistant fixes a problem (its own fix rounds, or a "Fix the last error" request), Manimo saves the problem and the few lines that fixed it, on this PC only. Later fix requests include the two or three closest saved fixes, a few hundred tokens at most, and nothing extra when none match. Switch it off, or forget everything, in AI settings. It keeps at most 200 fixes, and skips fixes that were whole rewrites.
- **Saved fixes list** (AI settings, See and manage): read every saved fix, see how often it was reused, delete one, **copy all as a fix pack** to share as plain text, and **import** a pack someone shared. Imported fixes are checked: only short removed/added code lines are accepted, tags are removed, and repeats are skipped.
- Libraries you install are allowed in the assistant's own code too, and the assistant is told which ones are installed, so it does not invent imports. `os`, `subprocess` and other system modules are still blocked.

## 1.9.10
- **Pictures of problems cost far less.** Attach, paste or drop a picture in the assistant. It is shrunk on your PC and read once into text by a short request; you check and correct the text, and the picture is never sent again.
- **Solve first, then animate.** For a new problem the assistant first gives a short worked solution (about 800 tokens). Press "Looks right: animate it" to get the animation, or "I will correct it". The switch "Solve first" turns this off.
- **Token estimate** under the message box shows roughly what a send will cost before you press Send.
- **One top bar.** Windows' own title bar is gone; minimize, maximize and close now sit in Manimo's own bar. Drag the empty part of the bar to move the window, double-click it to maximize or restore. Edge and corner resizing and window snapping still work. (`--native-title` brings the Windows bar back.)
- Fixed: a saved assistant model name the Claude Code agent does not know (such as `sonnet5.5`) no longer stops requests; Manimo retries with the agent's default model.

## 1.9.9
- **Layouts** (View menu, or Settings, Look): Classic, VS Code (an activity bar of views on the left and a status bar along the bottom), Top and bottom, Preview first, and Cinema (a big preview with a narrow code column). Each remembers its own split, and you can drag the divider in all of them.
- A View menu with the layouts, interface size, and the Project and Assistant panels.

## 1.9.8
- **Interface size** (Settings, Look): Compact (the new default, about 10% smaller so more fits on the screen), Normal and Large.
- The update message is now a small popup at the bottom left. It shows the download progress, can be folded away (Run in background) while the download carries on, and offers Install and restart when it is ready. It no longer moves the page.
- Fixed: the layout check wrongly reported an error for scenes that use `self.voiceover`. The assistant's own self-check had the same flaw.
- Tests for the code check and the skill modes.

## 1.9.7
- Fixed: the code-check panel opened out of sight above the editor; it now shows above the status bar.
- Fixed: the update bar pushed the toolbar and editor out of place while it showed.

## 1.9.6
- The AI assistant uses the updated skill pack: problem-solving, theory lessons, first-year exam mode and narration guides, loaded only when a request needs them.
- Prompt library: ready problem and theory prompts (mechanics, geometry, quantum, thermodynamics, Fourier, relativity).
- Code check: pasted or typed code is checked before rendering (syntax, missing scene, names that do not exist, unsafe imports), with an optional layout check.
- 14 curated Kokoro voices, grouped as female and male.
- Update check: Manimo looks for a newer release on GitHub, downloads it in the background, verifies its checksum and offers to install it.
- The Manim CE and LaTeX download (Settings) can use an add-on pack from the release, with a fallback.
## 1.9.5
- Optional installer component **Manim Community Edition and LaTeX** (offline, about 300 MB): trimmed TeX Live, `MathTex` and `Tex` render with no network.
- Automatic tests in `tests/` (66 fast tests, plus real-render tests behind `MANIMO_SLOW=1`).

## 1.9.4
- **My videos** library with cover pictures; **Speak text** and **Cover picture** tools in Compose.
- Burned-in captions and **Share for** presets (YouTube, Reels/Shorts/TikTok, Instagram post, WhatsApp) in Compose.
- Tall and square example scenes.

## 1.9.3
- **Edit video** button in the preview: edit one finished video in Compose, with or without a project.

## 1.9.2
- **Video shape** setting (same as code, 16:9, 9:16, 1:1, 4:3, 3:4). Tall and square scenes now render and export at their real shape, in the preview and in Compose.

## 1.9.1
- Video sits in its own tile in the preview and in Compose; Project panel actions became icons; Compose moved to a labelled top-bar button.
- Report a problem opens your email app; About credits Claude, ManimGX and Manim Community Edition.
- Fixed: the window could open another local site when the first port was busy (exclusive port bind).

## 1.9.0
- Layout restructure: preview-only right pane, collapsible Project and Assistant side panels, icon toolbar with tooltips, Report a problem in Help.

## 1.8 and earlier
- AI assistant (local Claude Code agent, Anthropic API key, OpenAI-compatible) with a safety and render-check loop and a skill pack.
- Microphone and camera Narrate; script and timestamp export; offline Kokoro voices.
- Hover explanations, Learn dialog, quick settings, four looks, tabbed Settings.
- `.mo` projects, scene status, and the Compose video editor (cut, trim, fade, music, camera overlay, voice-over, export with chapters and subtitles).
