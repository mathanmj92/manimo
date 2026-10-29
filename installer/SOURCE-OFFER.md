# Source code for the third-party programs in the Manimo installer

Manimo's own code is MIT licensed and is in this repository. The installer also carries other people's programs. Some of them are under the GNU General Public License (GPL) or Lesser GPL (LGPL), which means you are entitled to their source code. This page says where to get it.

The complete list of components and licences is in [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

## Components whose source you may ask for

| Component | Where it appears | Licence | Source |
|---|---|---|---|
| pdfTeX and the TeX Live programs | Optional "Manim Community Edition and LaTeX" component | GPL-2.0-or-later | https://tug.org/texlive/svn/ and https://github.com/TeX-Live/texlive-source |
| dvisvgm | Same optional component | GPL-3.0-or-later | https://github.com/mgieseking/dvisvgm |
| TeX Live macro packages and fonts | Same optional component | Various (LPPL, GPL, SIL OFL, others) | https://tug.org/texlive/ (each package lists its licence) |
| ManimGX 0.1.1 | Core app | Several, including GPL-2.0-or-later and LGPL-2.1-or-later parts | https://github.com/academa-labs/manimgx and https://pypi.org/project/manimgx/ |
| FFmpeg (through `imageio-ffmpeg` and PyAV) | Core app and the optional component | LGPL-2.1-or-later or GPL, depending on the build | https://ffmpeg.org/download.html, https://github.com/imageio/imageio-ffmpeg and https://github.com/PyAV-Org/PyAV |
| Pango, GLib, HarfBuzz, Cairo (inside the ManimPango and pycairo wheels) | Optional component | LGPL, MIT, MPL | https://pypi.org/project/ManimPango/ and https://pypi.org/project/pycairo/ |
| Python 3.13 | Core app | PSF licence | https://www.python.org/downloads/source/ |

The exact versions are the ones in the installer you downloaded: see Help, then Check my setup, inside Manimo, and the file names under `python\Lib\site-packages` in the install folder.

## If you cannot get the source from those links

Write to **mathannits92@gmail.com** with the Manimo version (Help, About) and the component you need. The corresponding source code will be provided, or you will be pointed to the exact upstream release it came from. This offer is valid for at least three years from the date of each release.

## Replacing or removing the parts

You can leave the optional LaTeX component unticked when you install Manimo; the core app does not need it. Components under LGPL (for example the libraries inside ManimPango and PyAV) are ordinary files in the install folder and can be replaced with your own builds of the same versions.
