<#
  Builds build\cache\texlive-lite: a small, relocatable TeX Live tree with only what Manim Community Edition needs
  (latex + dvisvgm + the packages of Manim's default Tex template). Called by Build-Manimo.ps1; run it by hand to rebuild.

  Needs internet once (TeX Live is fetched from the CTAN mirror network). The result is cached; delete
  build\cache\texlive-lite to force a rebuild.
#>
[CmdletBinding()]
param([switch]$Force)
$ErrorActionPreference = 'Stop'
$root  = Split-Path $PSScriptRoot -Parent
$cache = Join-Path $root 'build\cache'
$lite  = Join-Path $cache 'texlive-lite'
$work  = Join-Path $cache 'texlive-work'
$repo  = 'https://mirror.ctan.org/systems/texlive/tlnet'
# Packages Manim's default template loads (babel, amsmath, amssymb, dsfont, setspace, tipa, relsize, textcomp, mathrsfs,
# calligra, wasysym, ragged2e, physics, xcolor, microtype, lmodern, standalone/preview) plus dvips (dvisvgm needs its PostScript headers).
$packages = 'latex-bin latex latex-fonts amsmath amsfonts babel babel-english standalone preview doublestroke setspace tipa relsize jknapltx rsfs calligra wasysym ragged2e physics xcolor graphics graphics-def microtype dvisvgm tools lm dvips'.Split(' ')

if ((Test-Path (Join-Path $lite 'bin\windows\latex.exe')) -and -not $Force) { Write-Host "texlive-lite is already built: $lite"; return }
foreach ($d in $work, $lite) { if (Test-Path $d) { Remove-Item $d -Recurse -Force } }
New-Item -ItemType Directory -Force -Path $work | Out-Null

function Retry([scriptblock]$Do, [string]$What) {
    foreach ($try in 1..4) {
        try { & $Do; return } catch { Write-Host "$What failed (attempt $try): $($_.Exception.Message)" }
        Start-Sleep -Seconds (5 * $try)
    }
    throw "$What failed after 4 attempts."
}

# --- the TeX Live net installer
$zip = Join-Path $cache 'install-tl.zip'
if (-not (Test-Path $zip)) { Retry { Invoke-WebRequest "$repo/install-tl.zip" -OutFile $zip -UseBasicParsing -TimeoutSec 180 } 'Downloading the TeX Live installer' }
$inst = Join-Path $work 'installer'
Expand-Archive $zip $inst -Force
$bat = (Get-ChildItem $inst -Recurse -Filter install-tl-windows.bat | Select-Object -First 1).FullName

# --- install the bare infrastructure, per user, portable (no registry, no PATH change)
$tl = Join-Path $work 'tl'
$profileText = @"
selected_scheme scheme-infraonly
TEXDIR $tl
TEXMFLOCAL $tl\texmf-local
TEXMFSYSVAR $tl\texmf-var
TEXMFSYSCONFIG $tl\texmf-config
TEXMFVAR $tl\texmf-var
TEXMFCONFIG $tl\texmf-config
TEXMFHOME $tl\texmf-home
instopt_adjustpath 0
instopt_adjustrepo 1
instopt_letter 0
instopt_portable 1
instopt_write18_restricted 1
tlpdbopt_autobackup 0
tlpdbopt_create_formats 1
tlpdbopt_desktop_integration 0
tlpdbopt_file_assocs 0
tlpdbopt_generate_updmap 0
tlpdbopt_install_docfiles 0
tlpdbopt_install_srcfiles 0
tlpdbopt_post_code 1
tlpdbopt_w32_multi_user 0
"@
$profilePath = Join-Path $work 'tl.profile'
Set-Content $profilePath $profileText -Encoding ascii
$ErrorActionPreference = 'Continue'
Retry {
    & cmd /c "`"$bat`" -no-gui -profile `"$profilePath`" -repository $repo > `"$work\install-tl.log`" 2>&1"
    if (-not (Test-Path "$tl\bin\windows\tlmgr.bat")) { throw 'install-tl did not finish' }
} 'Installing TeX Live'
Retry {
    & "$tl\bin\windows\tlmgr.bat" install --no-persistent-downloads @packages *> "$work\tlmgr.log"
    $missing = Select-String -Path "$work\tlmgr.log" -Pattern 'not present in repository|could not' -ErrorAction SilentlyContinue
    if ($missing) { Write-Host ($missing | ForEach-Object Line); throw 'some packages could not be fetched' }
    if (-not (Test-Path "$tl\texmf-dist\tex\latex\amsmath")) { throw 'amsmath is missing after the install' }
} 'Installing the LaTeX packages'
$ErrorActionPreference = 'Stop'

# --- trim: remove everything Manim never touches, then rebuild the file database and drop the installer's own tools
$texmf = Join-Path $tl 'texmf-dist'
foreach ($rel in 'doc','source','fonts\afm','fonts\opentype','fonts\source','fonts\type1\public\cm-super','tex\luatex','tex\lualatex','tex\xelatex','tex\context','scripts','makeindex','bibtex','tex\latex\adjustbox') {
    $p = Join-Path $texmf $rel
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}
Get-ChildItem (Join-Path $tl 'texmf-var\web2c') -Directory | ForEach-Object {
    Get-ChildItem $_.FullName -Filter *.fmt | Where-Object { $_.Name -ne 'latex.fmt' } | Remove-Item -Force
}
Get-ChildItem (Join-Path $tl 'texmf-var\web2c') -Directory | Where-Object { -not (Get-ChildItem $_.FullName -Filter *.fmt) } | Remove-Item -Recurse -Force
& "$tl\bin\windows\mktexlsr.exe" "$texmf" "$tl\texmf-var" | Out-Null

# --- assemble the shipped tree
New-Item -ItemType Directory -Force -Path (Join-Path $lite 'bin\windows') | Out-Null
$keepExe = 'latex.exe','pdftex.exe','dvisvgm.exe','kpsewhich.exe'
Get-ChildItem "$tl\bin\windows" -File | Where-Object { $keepExe -contains $_.Name -or ($_.Extension -eq '.dll' -and $_.Name -notmatch '^(lua|luahbtex|luatex)') } | Copy-Item -Destination (Join-Path $lite 'bin\windows')
foreach ($d in 'texmf-dist','texmf-var') { Copy-Item (Join-Path $tl $d) (Join-Path $lite $d) -Recurse }
foreach ($d in 'texmf-local','texmf-config') { New-Item -ItemType Directory -Force -Path (Join-Path $lite $d) | Out-Null }
foreach ($f in 'texmf.cnf','LICENSE.TL','LICENSE.CTAN','release-texlive.txt') { if (Test-Path (Join-Path $tl $f)) { Copy-Item (Join-Path $tl $f) $lite } }
New-Item -ItemType Directory -Force -Path (Join-Path $lite 'tlpkg') | Out-Null
Copy-Item (Join-Path $tl 'tlpkg\tlpobj') (Join-Path $lite 'tlpkg\tlpobj') -Recurse   # one small file per package: names, versions, licences, file lists
Get-ChildItem (Join-Path $lite 'tlpkg\tlpobj') | Where-Object { $_.Name -match '^(lua|tlperl|tlgs|texlive\.infra|texlive-scripts)' } | Remove-Item -Force   # tools that are not shipped

$mb = (Get-ChildItem $lite -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("texlive-lite built: {0:N1} MB in {1}" -f $mb, $lite)
