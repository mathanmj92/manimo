# Changelog

All notable changes to Manimo. Versions follow the installer (`installer/Manimo.iss`).

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
