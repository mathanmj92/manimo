# Manimo tests

Standard-library `unittest` only. Run from the project folder with Manimo's private Python:

    %LOCALAPPDATA%\Manimo\python\python.exe -m unittest discover -s tests -v

- `test_server_helpers.py` - `video_size`, `code_shape`, scene discovery, constants (`app/server.py`).
- `test_project.py` - project create/open, `scene_hash`, `set_timeline`, `edit_video`, `_inside` (`app/project.py`).
- `test_http.py` - a real server on a free port: token, Host check, `/api/ping`, exclusive port bind.
- `test_render_slow.py` - real ManimGX renders (16:9 and 9:16 at 480p), checked with ffmpeg. **Skipped** unless
  `MANIMO_SLOW=1` (PowerShell: `$env:MANIMO_SLOW = "1"`). Takes a while and needs the render stack.

Fast tests take about a second. Every test works in a temp folder it deletes afterwards, and none touch
`app/`, the Recent list or your Documents folder.
