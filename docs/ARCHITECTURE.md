# Architecture

Manimo is a thin desktop shell around a local web app.

```
desktop.py   pywebview window (WebView2). Starts server.py on 127.0.0.1, opens the page, handles
             double-clicked .mo files and a second launch (focus the running window).
server.py    ThreadingHTTPServer. /api/* routes, /files/<id>/<name> with HTTP Range, token + Host checks,
             exclusive port bind. Builds the render command, runs jobs, parses progress and errors.
project.py   .mo projects: scenes, renders, the Compose timeline, ffmpeg export, quick edits.
voice.py     Offline Kokoro narration; the self.say / self.voiceover compatibility for scenes.
ai.py        The assistant: providers, the write-check-render-fix loop, the skill pack in app/ai/skill.
assets/      index.html, app.css, tokens.css (looks via data-look), app.js, project.js, library.js,
             prompt.js. No framework. vendor/editor.js is the bundled CodeMirror 6 (source in editor/).
```

## A render, end to end

1. The page posts code, scene, quality, **shape** and fps to `/api/render`.
2. `server.video_size(quality, shape, code)` picks the pixel size: the quality is the shorter side. With shape
   `auto` it reads `config.pixel_width, config.pixel_height` from the code and falls back to 16:9.
3. The job runs `python -m manimgx render ... -r WxH` (or `manim render ... -r W,H` for Manim CE) in a work folder;
   progress is estimated for ManimGX and measured for Manim CE.
4. The finished MP4 is served from `/files/...` and played in a tile sized to the video's real shape.

## Projects and Compose

A project is a folder with `project.mo` (JSON), `scenes/`, `renders/`, `recordings/`, `assets/`, `exports/`.
A scene is "up to date" when `scene_hash(code, scene, settings)` matches the hash saved with its render.
Compose export builds one ffmpeg `filter_complex`: `fps=` before `trim`, scale and pad to the export shape,
concat, optional camera overlay, optional burned captions (`subtitles` filter), music mixed with `amix normalize=0`.
"Edit video" with no project open uses a hidden quick project under `Documents\Manimo Projects\Quick edits`.

## Safety

Code from the assistant or the clipboard is scanned before it runs. The server binds `127.0.0.1`, requires the
per-launch token and Host header, serves only allow-listed file types and opens only allow-listed links.

## Installer

`installer/Build-Manimo.ps1` caches the official Python installer and every wheel, stages the app, and compiles
`installer/Manimo.iss` with Inno Setup. Setup installs for the current user only. The optional component
"Manim Community Edition and LaTeX" adds Manim CE and a trimmed TeX Live; the app puts that LaTeX on PATH only for
Manim CE render processes.
