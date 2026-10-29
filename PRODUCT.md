# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
Plain static HTML and CSS (user's choice). Surface: the Manimo landing page, in `site/`.

## Users
Teachers, students, tutors and educators who want moving maths and science diagrams, with narration, without learning Python. A secondary audience: people who already write Manim or ManimGX code and want a faster workflow. Typical situation: preparing a lecture or a lesson video on a Windows laptop, often offline or on a slow connection.

## Product Purpose
Manimo is a Windows desktop app that turns animation code (ManimGX and Manim) into finished video on the user's own PC. It gives a live preview, one-click rendering, an AI helper that writes and checks animation code, a built-in narration voice, a project folder for a whole lesson, and a pop-up editor (Compose) that joins the rendered scenes into one finished video. Success: a non-programmer gets from an idea to a narrated, edited lesson video without leaving the app.

## Positioning
Everything runs on the user's PC: rendering, preview, narration voices and editing need no account, and the installer includes what it needs to work offline. The AI helper is optional and can use an assistant already installed on the PC (for example Claude Code) or the user's own API key. A neighbouring tool would not truthfully claim the whole chain in one app: write, render, narrate, edit.

## Operating Context
Windows desktop app, installed per user. Code is ManimGX Python (`import manimgx as m`) or Manim Community code. Rendering uses ManimGX (a GPU engine). Narration uses the Kokoro voice model (English: Adam, Echo, Nicole, Lewis) running locally. Projects are folders with a `project.mo` file. Export produces MP4 with chapters and subtitles.

## Capabilities and Constraints
Confirmed and tested during development:
- Editor with autocomplete, hover explanations of names, options and numbers, find and replace, layout notes that jump to the line.
- Start Rendering, Present (slideshow that pauses at each section), scene picker, quality 480p to 4K, output folder.
- Runs ManimGX code, and Manim Community code when Manim is added from inside the app.
- Ask AI: writes a scene, checks every name exists, scans for unsafe code, checks for errors and overlapping text, and fixes problems. Connects to Claude Code or other agents on the PC, a Claude API key, or another model.
- Skill pack for 3Blue1Brown-style explainer code (also available as a Claude Code skill folder).
- Narration: `self.say(...)` and the `with self.voiceover(...)` style, four built-in voices, script export as .txt, .srt, .vtt, .json.
- Narrate: record your own voice and camera over a rendered video.
- Projects: one folder per lesson, out-of-date detection, render only what changed.
- Compose: auto-adds every rendered video, cut, trim, fade, background music, camera overlay, voice-over, undo, export 1080p/720p/480p/audio with chapters and subtitles.
- Four looks: Chalkboard, Blueprint (dark), Paper, Mint (light).
- Installer about 242 MB, works offline, per-user, no administrator rights; currently signed with a test certificate, so Windows shows an "unknown publisher" warning.
- Narration voices are English only. Tamil is not covered by the built-in voice.
- Windows only.

## Brand Commitments
Name: Manimo. Tagline: "Math, in motion." Made by Mathan Kumar P (Physics and Electrochemistry, Coimbatore, Tamil Nadu). Portfolio: https://mathanmj92.github.io/mathan/ . Built on ManimGX (Academa Team) and Manim Community Edition, each under its own licence.

## Evidence on Hand
- Real app screenshots can be captured from the running app.
- One real narrated lesson video: the capacitor charging scene (51 s, 854x480, narrated by the built-in Adam voice), rendered by Manimo.
- Price decision (user): free download for Windows.
- Absent, and must not be invented: testimonials, user counts, ratings, press, benchmarks against other tools, download statistics, a download URL.

## Product Principles
1. The picture teaches; the tool gets out of the way.
2. Works on the user's own machine, offline by default.
3. Every claim on the page is something the app does today.
4. Plain words first; code and jargon are explained, never assumed.
5. A whole lesson, not a single clip.

## Accessibility & Inclusion
Users include people new to programming and people on modest laptops and slow connections. The page must read well with keyboard only, at phone width, and with reduced motion.
