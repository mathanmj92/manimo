# Contributing to Manimo

Thanks for helping. Manimo is a small, plain codebase on purpose: Python standard library on the back end, plain JavaScript on the front end, no frameworks.

## Set up

1. Install Python 3.13, then `python -m pip install -r app\requirements.txt`.
2. Get the voice model: `powershell -ExecutionPolicy Bypass -File tools\Get-Models.ps1`.
3. Run `python app\desktop.py` (native window) or `python app\server.py --no-window` (server only).

## Before you open a pull request

- Run the tests: `python -m unittest discover -s tests -t .` (and with `MANIMO_SLOW=1` if you touched rendering or export).
- Add or update a test for any pure helper you change.
- Check the JavaScript parses: `node --check app\assets\app.js` (and the other files you changed).
- Look at the app yourself in the dark and in a light look (Paper), at a wide window and a narrow one. Say what you did not check.

## Style

- Match the surrounding code: naming, comment density, and idiom. Comments say why, not what.
- No new dependency or framework unless there is a strong reason. Say why in the pull request.
- Plain words in the interface: sentence case, a button says what happens, errors say what to do next.
- Keep the app usable offline. Anything that touches the network must be optional and visible to the user.
- PowerShell scripts run in Windows PowerShell 5.1: no `&&`, and no non-ASCII literals (use `[char]` codes or entities).

## Reporting a problem

Use **Help, Report a problem** in the app, or open an issue and paste the "Check my setup" text. Please do not include API keys or private code.

## Licence

By contributing you agree your work is released under the repository's [MIT licence](LICENSE).
