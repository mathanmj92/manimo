<#
  Builds dist\Manimo-Setup-<version>.exe with Inno Setup 7.

    .\Build-Manimo.ps1                       unsigned build
    .\Build-Manimo.ps1 -TestSign             signed with a self-made test certificate (shows a publisher name, but Windows
                                              does NOT trust it, so SmartScreen still warns). For checking the signing pipeline only.
    .\Build-Manimo.ps1 -Pfx cert.pfx -PfxPassword (Read-Host -AsSecureString)
                                              signed with a real code-signing certificate (what you ship to the public)

  Needs internet once, to fill build\cache with the official Python installer and every wheel.
#>
[CmdletBinding()]
param(
    [switch]$TestSign,
    [string]$Pfx,
    [securestring]$PfxPassword,
    [string]$PythonVersion = '3.13.15',
    [string]$TimestampUrl = 'http://timestamp.digicert.com'
)
$ErrorActionPreference = 'Stop'
$root   = Split-Path $PSScriptRoot -Parent
$cache  = Join-Path $root 'build\cache'
$wheels = Join-Path $cache 'wheels'
$pyExe  = Join-Path $cache "python-$PythonVersion-amd64.exe"
New-Item -ItemType Directory -Force -Path $cache, $wheels, (Join-Path $root 'dist') | Out-Null

# --- tools
$iscc = @("$env:ProgramFiles\Inno Setup 7\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Inno Setup 7 was not found. Install it from jrsoftware.org/isinfo.php' }

# --- art (regenerated only when missing)
$art = Join-Path $PSScriptRoot 'art'
if (-not (Test-Path (Join-Path $art 'wizard-large-328.bmp'))) { & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $art 'Make-Art.ps1') | Out-Null }

# --- payload: official Python installer (signature checked) + every wheel
if (-not (Test-Path $pyExe)) {
    Write-Host "Downloading Python $PythonVersion from python.org ..."
    Invoke-WebRequest "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe" -OutFile $pyExe -UseBasicParsing
}
$sig = Get-AuthenticodeSignature $pyExe
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
    Remove-Item $pyExe -Force
    throw "The Python installer is not signed by the Python Software Foundation (status: $($sig.Status))."
}
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw 'A local Python is only needed to run "pip download" while building. Install any Python 3.' }
# wheels already downloaded are kept, so a rebuild only fetches what is missing
# proxy_tools (needed by pywebview) is published only as source; it is pure Python, so build it into a universal wheel here.
$ErrorActionPreference = 'Continue'   # pip writes retry warnings to stderr; judge by exit code instead
& $py -m pip wheel proxy_tools --no-deps -w $wheels --disable-pip-version-check --retries 8 --timeout 30 -q 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Could not build the proxy_tools wheel.' }
foreach ($try in 1..4) {   # the network can drop; files already fetched are kept between attempts
    & $py -m pip download -r (Join-Path $root 'app\requirements.txt') -d $wheels --find-links $wheels --only-binary=:all: --platform win_amd64 --python-version 3.13 --implementation cp --disable-pip-version-check --retries 8 --timeout 30 -q 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    Write-Host "pip download attempt $try failed, retrying ..."
}
if ($LASTEXITCODE -ne 0) { throw 'pip download failed.' }
$ErrorActionPreference = 'Stop'

# --- optional component "Manim Community Edition and LaTeX": its own wheels (pinned in requirements-ce.txt) and a trimmed TeX Live
$wheelsCe = Join-Path $cache 'wheels-ce'
New-Item -ItemType Directory -Force -Path $wheelsCe | Out-Null
$reqCe = Join-Path $PSScriptRoot 'requirements-ce.txt'
$ErrorActionPreference = 'Continue'
foreach ($try in 1..4) {   # srt (needed by Manim CE) is published only as source: build it into a universal wheel
    & $py -m pip wheel srt --no-deps -w $wheelsCe --disable-pip-version-check --retries 8 --timeout 30 -q 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    Write-Host "building the srt wheel, attempt $try failed, retrying ..."
}
if ($LASTEXITCODE -ne 0) { throw 'Could not build the srt wheel.' }
foreach ($try in 1..4) {
    & $py -m pip download -r $reqCe -d $wheelsCe --find-links $wheelsCe --find-links $wheels --only-binary=:all: --platform win_amd64 --python-version 3.13 --implementation cp --disable-pip-version-check --retries 8 --timeout 30 -q 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    Write-Host "pip download (Manim CE) attempt $try failed, retrying ..."
}
if ($LASTEXITCODE -ne 0) { throw 'pip download for Manim CE failed.' }
$ErrorActionPreference = 'Stop'
# files the core app already ships are installed from there: do not carry them twice
Get-ChildItem $wheelsCe -Filter *.whl | Where-Object { Test-Path (Join-Path $wheels $_.Name) } | Remove-Item -Force
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Make-Latex.ps1')
if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $cache 'texlive-lite\bin\windows\latex.exe'))) { throw 'The LaTeX bundle could not be built.' }
# disk space the component needs once installed: its TeX tree plus the unpacked wheels (about twice their size)
$ceMB = [math]::Ceiling((((Get-ChildItem (Join-Path $cache 'texlive-lite') -Recurse -File | Measure-Object Length -Sum).Sum) + 2 * ((Get-ChildItem $wheelsCe -File | Measure-Object Length -Sum).Sum)) / 1MB / 10) * 10

# --- the editor bundle must exist
if (-not (Test-Path (Join-Path $root 'app\vendor\editor.js'))) { throw 'app\vendor\editor.js is missing. Run "node build.mjs" in the editor folder.' }

# --- signing
$isccArgs = @()
$signNote = 'unsigned'
if ($TestSign -or $Pfx) {
    $signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\' } | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    if (-not $signtool) { throw 'signtool.exe was not found (install the Windows SDK "Signing Tools").' }
    if ($Pfx) {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($PfxPassword))
        $who = '/f $q{0}$q /p $q{1}$q' -f $Pfx, $plain      # $q is Inno's own escape for a double quote
        $signNote = "signed with $Pfx"
    } else {
        $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like '*Manimo (test signing)*' -and $_.NotAfter -gt (Get-Date) } | Select-Object -First 1
        if (-not $cert) {
            $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=Manimo (test signing), O=Manimo' -CertStoreLocation Cert:\CurrentUser\My `
                -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 -NotAfter (Get-Date).AddYears(3)
        }
        $who = '/sha1 {0}' -f $cert.Thumbprint
        $signNote = 'signed with a self-made TEST certificate (not trusted by Windows)'
    }
    $cmd = '$q{0}$q sign /fd SHA256 {1} /tr {2} /td SHA256 /d $qManimo Setup$q $f' -f $signtool, $who, $TimestampUrl
    $isccArgs += '/DSign=1', ('/Smanimosign=' + $cmd)
}

$isccArgs += "/DCeMB=$ceMB"
& $iscc @isccArgs (Join-Path $PSScriptRoot 'Manimo.iss')
if ($LASTEXITCODE -ne 0) { throw "ISCC failed (exit code $LASTEXITCODE)." }
$exe = Get-ChildItem (Join-Path $root 'dist') -Filter 'Manimo-Setup-*.exe' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$s = Get-AuthenticodeSignature $exe.FullName
Write-Host ("`nBuilt {0}  ({1:N1} MB)`n  {2}`n  Authenticode status: {3}`n  SHA256: {4}" -f $exe.FullName, ($exe.Length / 1MB), $signNote, $s.Status, (Get-FileHash $exe.FullName).Hash)
