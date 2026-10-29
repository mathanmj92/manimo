# Changelog

All notable changes to Manimo. Versions follow the installer (`installer/Manimo.iss`).

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
