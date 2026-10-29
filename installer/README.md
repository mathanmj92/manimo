# Building and shipping the Manimo installer

## Decision: LaTeX for Manim Community Edition (1.9.5)
**Shipped: a trimmed TeX Live 2026 tree (pdfTeX `latex` + `dvisvgm` + only the packages Manim's template loads), as the optional,
unticked-by-default component "Manim Community Edition and LaTeX (offline, about 300 MB)".** Sizes:

| | Installer | Installed |
|---|---|---|
| Core only (component unticked) | 241.3 MB | about 670 MB |
| With the component | 334.9 MB (+93.6 MB) | about +300 MB (TeX tree 48 MB, the rest Manim CE with SciPy, PyAV and pango wheels) |

Why this one, and what was rejected:
- **Tectonic** (single exe + bundle cache) is smaller, but Manim CE drives `latex` -> `.dvi` -> `dvisvgm`, and `dvisvgm` needs a kpathsea
  texmf tree to find fonts; Tectonic keeps fonts in its own network bundle. Not a drop-in; rejected.
- **MiKTeX portable** installs packages on demand from the internet and is much larger once relocated. Rejected.
- **TeX Live** is relocatable (it finds `texmf.cnf` from the exe location), needs no admin, registry or PATH edit, and every part is
  redistributable (LPPL, GPL, OFL, GUST, Knuth; see `THIRD-PARTY-NOTICES.txt`; a per-package list ships in `texlive\tlpkg\tlpobj`).
  The infrastructure scheme plus the needed packages is 295 MB; trimmed (no docs, sources, LuaTeX, cm-super, afm, opentype, Perl, Ghostscript) it is **48 MB**.
- Known limit: the `calligra` font is Metafont only, so `\calligra` glyphs would need `mf`; the package loads and Manim's default template renders.
- The TeX Live net installer is fetched over HTTPS from the CTAN mirror redirector without a gpg signature check.

Proof: `MathTex(r"\int_0^1 x^2\,dx = \tfrac13")` and `Tex` with `\frac`, `\sum`, `\vec`, `\hbar` rendered with Manim CE 0.22 from a relocated copy
of the tree (PATH reduced to the bundled tools, every non-loopback connection blocked inside Python, dead HTTP proxy), and again from a real silent install.

## How the component works
- `Make-Latex.ps1` builds `build\cache\texlive-lite` once (cached; delete it to rebuild). `Build-Manimo.ps1` also caches the Manim CE wheels in
  `build\cache\wheels-ce` (pinned by `requirements-ce.txt`, retried on network errors, `srt` built from source into a wheel) and calls that script.
- Inno `[Components]` item `ce`, unticked by default. Silent: `Manimo-Setup-1.9.5.exe /VERYSILENT /COMPONENTS="core,ce"`.
- Setup runs `pip install --no-index` from the bundled wheels, then checks `import manim`, `latex --version` and `dvisvgm --version`.
- The app finds `{app}\texlive\bin\windows` next to its private Python and puts it first on PATH only for the Manim CE render process
  (`server.tex_env`); the user's PATH and registry are never touched. Settings > Files and engines and "Check my setup" show the LaTeX version.
- Unticking the component on a later reinstall removes the TeX tree and the packages it added. Uninstall deletes the whole Manimo folder.
- Testing the installer on a PC that already has Manimo: Python's installer keeps one per-user registration for 3.13.15, so a second copy
  makes Setup (and its uninstaller) remove the first copy's Python. Back up first, or use another Windows account.

```powershell
cd installer
.\Build-Manimo.ps1                 # unsigned
.\Build-Manimo.ps1 -TestSign       # signed with a self-made certificate: checks the pipeline, NOT trusted by Windows
.\Build-Manimo.ps1 -Pfx my.pfx -PfxPassword (Read-Host -AsSecureString)   # real certificate
```

Output: `dist\Manimo-Setup-1.9.5.exe` (about 241 MB core, 335 MB with the Manim CE + LaTeX files; works fully offline).
First build needs internet to fill `build\cache` (official Python installer, signature-checked, plus every wheel).

## What the installer does
Welcome (art, slogan) -> shortcut choice -> installs to `%LOCALAPPDATA%\Manimo` (no admin rights) -> private Python 3.13 -> ManimGX and the native-window parts (pywebview) from the
bundled wheels -> self-check -> "Open Manimo now". It removes the old "ManimGX Studio" test build if it finds one. Uninstall is in
Settings > Apps and also unregisters the private Python. Silent install: `Manimo-Setup-1.9.5.exe /VERYSILENT /SUPPRESSMSGBOXES`.

## Making Windows trust it (the part money buys)
A self-signed certificate proves nothing to Windows, so SmartScreen still warns. To remove the warning for the public you need a
certificate from a company Windows already trusts:

| Option | Roughly | Notes |
|---|---|---|
| Microsoft Trusted Signing (Azure) | about $10 per month | Cheapest; needs a verifiable business or individual identity |
| OV code-signing certificate | $100-250 per year | Reputation builds slowly, early downloads may still warn |
| EV code-signing certificate | $250-500 per year | Trusted immediately; hardware token |
| SignPath Foundation | free | Only for open-source projects |

Then run `Build-Manimo.ps1` with your certificate. Nothing else changes.

## Art and icon
`art\Make-Art.ps1` draws the icon, the tall welcome picture and the small header logo from code. Edit colours or text there and re-run it.

## Licences (check before publishing)
ManimGX declares many licences, including GPL-2.0-or-later and GPL-3.0-or-later components. Shipping its wheel inside your installer
means you must meet those terms (notices are included in `THIRD-PARTY-NOTICES.txt`; GPL parts may require offering their source).
Get this confirmed before distributing publicly.

