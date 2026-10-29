<#
  ManimGX Studio installer (Windows 10/11, Windows PowerShell 5.1)

  Two modes:

  ONLINE (installer\ + app\ folders, no payload)
    1. Looks for Python 3.13+ on this PC (ManimGX needs it).
       Not found -> asks to open python.org's latest-download page, waits for you to install it, re-checks.
    2. Copies the app into %LOCALAPPDATA%\ManimGX Studio
    3. Creates a private virtual environment and pip-installs every dependency
    4. Creates a Desktop shortcut and a Start Menu entry, then launches the app

  OFFLINE (payload with python-installer.exe, wheels\ and app\; this is what the Setup .exe carries)
    Same steps, but Python 3.13 is installed privately from the payload and every package comes from
    the bundled wheels. No internet, no admin rights, and the user's own Python is left alone.

  Switches:  -PayloadZip <zip> | -PayloadDir <folder>  -Silent  -NoShortcut  -NoLaunch  -InstallDir <path>
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'ManimGX Studio'),
    [string]$PayloadZip,
    [string]$PayloadDir,
    [switch]$Silent,
    [switch]$NoShortcut,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
$AppName    = 'ManimGX Studio'
$MinPython  = [version]'3.13'   # manimgx wheels are cp313-abi3 and require Python >= 3.13
$PythonUrl  = 'https://www.python.org/downloads/'
$SourceDir  = Join-Path $PSScriptRoot '..\app'
$AppDir     = Join-Path $InstallDir 'app'
$VenvDir    = Join-Path $InstallDir 'venv'
$LogFile    = Join-Path $InstallDir 'install.log'
$script:form = $null

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# ---------------------------------------------------------------- UI helpers
function Pump { if ($script:form) { [System.Windows.Forms.Application]::DoEvents() }; Start-Sleep -Milliseconds 60 }

function Write-Log([string]$Text) {
    Add-Content -Path $LogFile -Value ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Text) -Encoding UTF8
}

function Set-Status([string]$Text, [int]$Step = -1) {
    Write-Log $Text
    if (-not $script:form) { Write-Host $Text; return }
    $script:statusLabel.Text = $Text
    if ($Step -ge 0) {
        for ($i = 0; $i -lt $script:stepLabels.Count; $i++) {
            $l = $script:stepLabels[$i]
            if ($i -lt $Step)      { $l.Text = [string][char]0x2713 + '  ' + $script:stepNames[$i]; $l.ForeColor = [Drawing.Color]::FromArgb(34, 139, 94) }
            elseif ($i -eq $Step)  { $l.Text = [string][char]0x25CF + '  ' + $script:stepNames[$i]; $l.ForeColor = [Drawing.Color]::FromArgb(40, 80, 220) }
            else                   { $l.Text = [string][char]0x25CB + '  ' + $script:stepNames[$i]; $l.ForeColor = [Drawing.Color]::FromArgb(130, 135, 150) }
        }
        $script:bar.Style = 'Continuous'
        $script:bar.Value = [math]::Min(100, [int](($Step / $script:stepLabels.Count) * 100))
    }
    Pump
}

function Show-Box([string]$Text, [string]$Title, [string]$Buttons = 'OK', [string]$Icon = 'Information') {
    if ($Silent) { Write-Host "$Title - $Text"; return 'Cancel' }
    $owner = $null
    if ($script:form) { $owner = $script:form }
    return [System.Windows.Forms.MessageBox]::Show($owner, $Text, $Title, $Buttons, $Icon)
}

function New-InstallerWindow {
    $f = New-Object Windows.Forms.Form
    $f.Text = "$AppName Setup"
    $f.ClientSize = New-Object Drawing.Size(520, 330)
    $f.StartPosition = 'CenterScreen'
    $f.FormBorderStyle = 'FixedDialog'
    $f.MaximizeBox = $false
    $f.Font = New-Object Drawing.Font('Segoe UI', 9.5)
    $f.BackColor = [Drawing.Color]::FromArgb(250, 249, 246)

    $title = New-Object Windows.Forms.Label
    $title.Text = "Installing $AppName"
    $title.Font = New-Object Drawing.Font('Segoe UI Semibold', 17)
    $title.Location = New-Object Drawing.Point(28, 22)
    $title.AutoSize = $true
    $f.Controls.Add($title)

    $sub = New-Object Windows.Forms.Label
    $sub.Text = 'This takes a few minutes the first time. Please keep this window open.'
    $sub.ForeColor = [Drawing.Color]::FromArgb(90, 95, 110)
    $sub.Location = New-Object Drawing.Point(30, 58)
    $sub.AutoSize = $true
    $f.Controls.Add($sub)

    $script:stepNames  = @('Set up Python', 'Copy app files', 'Install dependencies', 'Create shortcuts', 'Launch')
    $script:stepLabels = @()
    $y = 98
    foreach ($n in $script:stepNames) {
        $l = New-Object Windows.Forms.Label
        $l.Text = [string][char]0x25CB + '  ' + $n
        $l.ForeColor = [Drawing.Color]::FromArgb(130, 135, 150)
        $l.Location = New-Object Drawing.Point(34, $y)
        $l.AutoSize = $true
        $f.Controls.Add($l)
        $script:stepLabels += $l
        $y += 27
    }

    $script:bar = New-Object Windows.Forms.ProgressBar
    $script:bar.Location = New-Object Drawing.Point(30, 250)
    $script:bar.Size = New-Object Drawing.Size(460, 10)
    $f.Controls.Add($script:bar)

    $script:statusLabel = New-Object Windows.Forms.Label
    $script:statusLabel.Location = New-Object Drawing.Point(30, 270)
    $script:statusLabel.Size = New-Object Drawing.Size(460, 40)
    $script:statusLabel.ForeColor = [Drawing.Color]::FromArgb(60, 65, 80)
    $f.Controls.Add($script:statusLabel)
    return $f
}

# ---------------------------------------------------------------- Python detection
function Get-PythonVersion([string]$Exe) {
    try {
        $out = & $Exe -c "import sys, venv, ensurepip; print('%d.%d.%d' % sys.version_info[:3])"
        if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
        return [version]($out | Select-Object -First 1).Trim()
    } catch { return $null }
}

function Find-Python {
    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($root in 'HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore', 'HKLM:\Software\WOW6432Node\Python\PythonCore') {
        if (-not (Test-Path $root)) { continue }
        foreach ($k in Get-ChildItem $root -ErrorAction SilentlyContinue) {
            $ip = Join-Path $k.PSPath 'InstallPath'
            if (-not (Test-Path $ip)) { continue }
            $p = Get-ItemProperty $ip -ErrorAction SilentlyContinue
            if ($p.ExecutablePath) { $candidates.Add($p.ExecutablePath) }
            elseif ($p.'(default)') { $candidates.Add((Join-Path $p.'(default)' 'python.exe')) }
        }
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        try { $e = & $py.Source -3 -c 'import sys; print(sys.executable)'; if ($e) { $candidates.Add($e.Trim()) } } catch {}
    }
    # The WindowsApps "python.exe" is a Store shortcut, not Python - skip it.
    foreach ($c in Get-Command python.exe -All -ErrorAction SilentlyContinue) {
        if ($c.Source -notlike '*\WindowsApps\*') { $candidates.Add($c.Source) }
    }
    $best = $null
    foreach ($c in ($candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique)) {
        $v = Get-PythonVersion $c
        if ($v -and $v -ge $MinPython -and (-not $best -or $v -gt $best.Version)) {
            $best = [pscustomobject]@{ Path = $c; Version = $v }
        }
    }
    return $best
}

function Update-SessionPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Get-OrInstallPython {
    Set-Status 'Looking for Python on this PC...' 0
    $found = Find-Python
    if ($found) { Set-Status ("Found Python {0}" -f $found.Version) 0; return $found }

    if ($Silent) { throw "Python $MinPython or newer was not found." }
    $ans = Show-Box ("$AppName needs Python $MinPython or newer, and it was not found on this PC.`n`n" +
                     "Open the official Python download page now?`n`n" +
                     "In the Python installer, tick  'Add python.exe to PATH'  and choose Install Now.") `
                    'Python is required' 'YesNo' 'Question'
    if ($ans -ne 'Yes') { throw 'Setup was cancelled because Python is required.' }
    Start-Process $PythonUrl

    while ($true) {
        $ans = Show-Box ("Install Python from the page that just opened, then come back here.`n`n" +
                         "When Python has finished installing, click Retry.") `
                        'Waiting for Python' 'RetryCancel' 'Information'
        if ($ans -ne 'Retry') { throw 'Setup was cancelled before Python was installed.' }
        Update-SessionPath
        Set-Status 'Checking for Python again...' 0
        $found = Find-Python
        if ($found) { Set-Status ("Found Python {0}" -f $found.Version) 0; return $found }
        $again = Show-Box ("Python still was not detected.`n`nMake sure the installer finished, then choose Retry. " +
                           "Choose Cancel to open the download page again.") 'Python not found yet' 'RetryCancel' 'Warning'
        if ($again -ne 'Retry') { Start-Process $PythonUrl }
    }
}

# ---------------------------------------------------------------- Running tools with a live status line
function Read-LastLine([string]$Path) {
    try {
        $fs = [IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
        $sr = New-Object IO.StreamReader($fs)
        $last = ''
        while (-not $sr.EndOfStream) { $l = $sr.ReadLine(); if ($l.Trim()) { $last = $l.Trim() } }
        $sr.Close(); return $last
    } catch { return '' }
}

function Invoke-Logged([string]$Exe, [string[]]$ArgList, [string]$Label) {
    $quoted = ($ArgList | ForEach-Object {
        if ($_ -match '^(\w+)=(.*\s.*)$') { $Matches[1] + '="' + $Matches[2] + '"' }   # Name="value with spaces" (Python setup style)
        elseif ($_ -match '\s') { '"' + $_ + '"' }
        else { $_ }
    }) -join ' '
    $out = Join-Path $env:TEMP 'mgx-out.txt'
    $err = Join-Path $env:TEMP 'mgx-err.txt'
    Remove-Item $out, $err -ErrorAction SilentlyContinue
    Write-Log "RUN $Exe $quoted"
    $p = Start-Process -FilePath $Exe -ArgumentList $quoted -PassThru -WindowStyle Hidden `
         -RedirectStandardOutput $out -RedirectStandardError $err
    $null = $p.Handle   # caches the process handle; without it Windows PowerShell 5.1 can return a $null ExitCode
    if ($script:form) { $script:bar.Style = 'Marquee'; $script:bar.MarqueeAnimationSpeed = 30 }
    while (-not $p.HasExited) {
        $line = Read-LastLine $out
        if ($line -and $script:form) {
            if ($line.Length -gt 70) { $line = $line.Substring(0, 70) + '...' }
            $script:statusLabel.Text = "$Label`n$line"
        }
        Pump
    }
    $p.WaitForExit()
    foreach ($f in $out, $err) { if (Test-Path $f) { Get-Content $f -ErrorAction SilentlyContinue | ForEach-Object { Write-Log "  $_" } } }
    if ($script:form) { $script:bar.Style = 'Continuous' }
    return $p.ExitCode
}

# ---------------------------------------------------------------- Shortcut + icon
function New-AppIcon([string]$Path) {
    $bmp = New-Object Drawing.Bitmap 256, 256
    $g = [Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $g.Clear([Drawing.Color]::Transparent)
    $r = 58; $d = $r * 2
    $gp = New-Object Drawing.Drawing2D.GraphicsPath
    $gp.AddArc(0, 0, $d, $d, 180, 90); $gp.AddArc(256 - $d, 0, $d, $d, 270, 90)
    $gp.AddArc(256 - $d, 256 - $d, $d, $d, 0, 90); $gp.AddArc(0, 256 - $d, $d, $d, 90, 90)
    $gp.CloseFigure()
    $g.FillPath((New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(59, 91, 219))), $gp)
    $pen = New-Object Drawing.Pen ([Drawing.Color]::White), 20
    $pen.StartCap = 'Round'; $pen.EndCap = 'Round'
    $pts = [Drawing.PointF[]]@(
        (New-Object Drawing.PointF 40, 160), (New-Object Drawing.PointF 78, 160), (New-Object Drawing.PointF 98, 96),
        (New-Object Drawing.PointF 128, 96), (New-Object Drawing.PointF 148, 160), (New-Object Drawing.PointF 178, 160),
        (New-Object Drawing.PointF 198, 96))
    $g.DrawCurve($pen, $pts, 0.55)
    $g.FillEllipse([Drawing.Brushes]::White, 188, 56, 28, 28)
    $g.Dispose()
    $ms = New-Object IO.MemoryStream
    $bmp.Save($ms, [Drawing.Imaging.ImageFormat]::Png)
    $png = $ms.ToArray(); $bmp.Dispose()
    $fs = [IO.File]::Create($Path); $w = New-Object IO.BinaryWriter($fs)
    $w.Write([uint16]0); $w.Write([uint16]1); $w.Write([uint16]1)            # ICONDIR: 1 image
    $w.Write([byte]0); $w.Write([byte]0); $w.Write([byte]0); $w.Write([byte]0) # 256x256, no palette
    $w.Write([uint16]1); $w.Write([uint16]32); $w.Write([uint32]$png.Length); $w.Write([uint32]22)
    $w.Write($png); $w.Close()
}

function New-Shortcut([string]$LnkPath, [string]$Target, [string]$Arguments, [string]$WorkDir, [string]$Icon) {
    $sh = New-Object -ComObject WScript.Shell
    $s = $sh.CreateShortcut($LnkPath)
    $s.TargetPath = $Target
    $s.Arguments = $Arguments
    $s.WorkingDirectory = $WorkDir
    $s.IconLocation = "$Icon,0"
    $s.Description = 'Render ManimGX animations to video'
    $s.Save()
}

# ---------------------------------------------------------------- Main install
function Install-App {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Write-Log "=== $AppName install, source=$SourceDir target=$InstallDir ==="

    # Offline payload (the Setup .exe carries a zip; a folder works too for testing)
    $payload = $null
    if ($PayloadZip) {
        Set-Status 'Unpacking installer files...' 0
        $payload = Join-Path $env:TEMP ('mgx-payload-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
        Expand-Archive -Path $PayloadZip -DestinationPath $payload -Force
    } elseif ($PayloadDir) { $payload = $PayloadDir }
    $offline = $payload -and (Test-Path (Join-Path $payload 'python-installer.exe'))
    $src = if ($offline) { Join-Path $payload 'app' } else { $SourceDir }

    # 1. Python
    if ($offline) {
        Set-Status 'Installing Python 3.13 (bundled, no internet needed)...' 0
        $pyHome = Join-Path $InstallDir 'python'
        $setupKeep = Join-Path $InstallDir '_setup'
        New-Item -ItemType Directory -Force -Path $setupKeep | Out-Null
        Copy-Item (Join-Path $payload 'python-installer.exe') $setupKeep -Force   # kept so Uninstall can remove Python cleanly
        if (-not (Test-Path (Join-Path $pyHome 'python.exe'))) {
            $code = Invoke-Logged (Join-Path $setupKeep 'python-installer.exe') @('/quiet', 'InstallAllUsers=0', "TargetDir=$pyHome",
                'Include_launcher=0', 'Include_test=0', 'Include_doc=0', 'PrependPath=0', 'Shortcuts=0', 'AssociateFiles=0') 'Installing Python 3.13...'
            if (($code -ne 0 -and $code -ne 3010) -or -not (Test-Path (Join-Path $pyHome 'python.exe'))) { throw "The bundled Python installer failed (exit code $code)." }
        }
        $python = [pscustomobject]@{ Path = (Join-Path $pyHome 'python.exe'); Version = [version]'3.13' }
    } else {
        $python = Get-OrInstallPython
    }

    # 2. Files
    Set-Status 'Copying app files...' 1
    if (-not (Test-Path (Join-Path $src 'server.py'))) { throw "App files not found next to the installer ($src)." }
    New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
    Copy-Item -Path (Join-Path $src '*') -Destination $AppDir -Recurse -Force
    Pump

    # 3. Dependencies
    $reqFile = Join-Path $AppDir 'requirements.txt'
    if ($offline) {
        # Bundled Python is already private to this app, so it is used directly (no venv needed).
        $venvPy = $python.Path
        $pyw = Join-Path (Split-Path $venvPy) 'pythonw.exe'
        Set-Status 'Installing ManimGX and its dependencies from the bundled files...' 2
        $code = Invoke-Logged $venvPy @('-m', 'pip', 'install', '--no-index', '--find-links', (Join-Path $payload 'wheels'),
                                        '-r', $reqFile, '--disable-pip-version-check') 'Installing ManimGX and its dependencies...'
        if ($code -ne 0) { throw 'Installing the bundled packages failed. See the log for details.' }
    } else {
        Set-Status 'Creating a private Python environment...' 2
        $venvPy = Join-Path $VenvDir 'Scripts\python.exe'
        $pyw = Join-Path $VenvDir 'Scripts\pythonw.exe'
        if (-not (Test-Path $venvPy)) {
            $code = Invoke-Logged $python.Path @('-m', 'venv', $VenvDir) 'Creating a private Python environment...'
            if ($code -ne 0 -or -not (Test-Path $venvPy)) { throw 'Could not create the Python environment.' }
        }
        $code = Invoke-Logged $venvPy @('-m', 'pip', 'install', '--upgrade', 'pip', '--disable-pip-version-check') 'Updating the package installer...'
        if ($code -ne 0) { throw 'Could not update pip. Check your internet connection and try again.' }
        $code = Invoke-Logged $venvPy @('-m', 'pip', 'install', '-r', $reqFile, '--disable-pip-version-check') `
                              'Installing ManimGX and its dependencies (this is the long step)...'
        if ($code -ne 0) { throw "Installing dependencies failed.`n`nCheck your internet connection and try again." }
    }
    $code = Invoke-Logged $venvPy @('-c', 'import manimgx as m; print(m.Scene)') 'Checking the installation...'
    if ($code -ne 0) { throw 'ManimGX installed but could not be loaded.' }
    $code = Invoke-Logged $venvPy @('-m', 'manimgx', '--version') 'Checking the ManimGX command...'
    if ($code -ne 0) { throw 'The ManimGX command did not start.' }

    # 4. Shortcuts
    Set-Status 'Creating shortcuts...' 3
    $server = Join-Path $AppDir 'server.py'
    $ico = Join-Path $AppDir 'icon.ico'
    New-AppIcon $ico
    if (-not $NoShortcut) {
        $desktop = [Environment]::GetFolderPath('Desktop')
        New-Shortcut (Join-Path $desktop "$AppName.lnk") $pyw "`"$server`"" $AppDir $ico
        $menu = Join-Path ([Environment]::GetFolderPath('Programs')) "$AppName.lnk"
        New-Shortcut $menu $pyw "`"$server`"" $AppDir $ico
    }
    Set-Content -Path (Join-Path $InstallDir 'Uninstall.ps1') -Encoding UTF8 -Value @"
`$ErrorActionPreference = 'SilentlyContinue'
Get-Process pythonw | Where-Object { `$_.Path -like '$InstallDir\*' } | Stop-Process -Force
Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) '$AppName.lnk')
Remove-Item (Join-Path ([Environment]::GetFolderPath('Programs')) '$AppName.lnk')
Set-Location `$env:TEMP
`$pySetup = '$InstallDir\_setup\python-installer.exe'
if (Test-Path `$pySetup) { Start-Process `$pySetup -ArgumentList '/uninstall','/quiet' -Wait }   # remove the bundled Python's registration
Remove-Item -Recurse -Force '$InstallDir'
Write-Host '$AppName was removed. Your rendered videos were not touched.'
"@

    # 5. Launch
    Set-Status 'Starting ManimGX Studio...' 4
    if (-not $NoLaunch) { Start-Process -FilePath $pyw -ArgumentList "`"$server`"" -WorkingDirectory $AppDir }
    Set-Status 'All done.' 5
    if ($script:form) {
        for ($i = 0; $i -lt $script:stepLabels.Count; $i++) {
            $script:stepLabels[$i].Text = [string][char]0x2713 + '  ' + $script:stepNames[$i]
            $script:stepLabels[$i].ForeColor = [Drawing.Color]::FromArgb(34, 139, 94)
        }
        $script:bar.Value = 100
        $script:statusLabel.Text = if ($NoShortcut) { "$AppName is installed." } else { "$AppName is installed. Use the shortcut on your Desktop any time." }
        Pump; Start-Sleep -Milliseconds 1600
    }
}

# ---------------------------------------------------------------- Entry point
$exitCode = 0
if ($Silent) {
    try { Install-App } catch { Write-Host "FAILED: $($_.Exception.Message)"; $exitCode = 1 }
    exit $exitCode
}

$script:form = New-InstallerWindow
$script:form.Add_Shown({
    try { Install-App }
    catch {
        Write-Log "FAILED: $($_.Exception.Message)"
        $script:exitCode = 1
        $ans = Show-Box ($_.Exception.Message + "`n`nA log was saved to:`n$LogFile`n`nOpen the log?") 'Setup could not finish' 'YesNo' 'Error'
        if ($ans -eq 'Yes') { Start-Process notepad.exe $LogFile }
    }
    $script:form.Close()
})
[void]$script:form.ShowDialog()
exit $script:exitCode
