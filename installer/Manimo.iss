; Manimo installer (Inno Setup 7). Fully offline: Python 3.13 and every package are inside the file.
; Build with installer\Build-Manimo.ps1, which prepares the payload and compiles this script.

#define AppName "Manimo"
#define AppVersion "1.9.5"
#define AppSlogan "Math, in motion."
#define PyInstaller "..\build\cache\python-3.13.15-amd64.exe"
; the build script passes the measured size of the optional component with /DCeMB=n
#ifndef CeMB
  #define CeMB 300
#endif

[Setup]
AppId={{B7C6F1E2-5B1F-4C9A-9D7E-3A2F8E4D6C11}
ChangesAssociations=yes
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
AppComments={#AppSlogan}
DefaultDirName={localappdata}\{#AppName}
DisableWelcomePage=no
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Manimo-Setup-{#AppVersion}
SetupIconFile=art\manimo.ico
UninstallDisplayIcon={app}\manimo.ico
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile=art\wizard-large-164.bmp,art\wizard-large-246.bmp,art\wizard-large-328.bmp
WizardSmallImageFile=art\wizard-small-55.bmp,art\wizard-small-83.bmp,art\wizard-small-110.bmp
Compression=lzma2/max
SolidCompression=yes
ShowLanguageDialog=no
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#AppName}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
#ifdef Sign
SignTool=manimosign
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
SetupWindowTitle=Install {#AppName}
WelcomeLabel1=Welcome to {#AppName}
WelcomeLabel2={#AppSlogan}%n%n{#AppName} turns animation code into video, right on your computer, using your graphics card.%n%nIt brings everything it needs. You do not need to install Python or anything else, and no internet connection is required. You can also tick Manim Community Edition and LaTeX on the next page to render Tex and MathTex with Manim, still with no download.%n%nSetup takes about a minute.
ButtonInstall=&Install
FinishedHeadingLabel={#AppName} is ready
FinishedLabelNoIcons={#AppName} has been installed.
FinishedLabel={#AppName} has been installed. Open it from the shortcut whenever you like.
BeveledLabel={#AppName}  Â·  {#AppSlogan}

[Types]
Name: "custom"; Description: "Choose what to install"; Flags: iscustom

[Components]
Name: "core"; Description: "{#AppName} (required)"; Types: custom; Flags: fixed
Name: "ce"; Description: "Manim Community Edition and LaTeX (offline, about {#CeMB} MB)"; ExtraDiskSpaceRequired: {#Int(CeMB) * 500000}

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#PyInstaller}"; DestDir: "{app}\_setup"; DestName: "python-installer.exe"; Flags: ignoreversion
Source: "..\build\cache\wheels\*"; DestDir: "{tmp}\wheels"; Flags: ignoreversion deleteafterinstall
Source: "..\app\*"; DestDir: "{app}\app"; Excludes: "__pycache__"; Flags: ignoreversion recursesubdirs createallsubdirs
; optional component: Manim Community Edition (wheels) and a trimmed, relocatable TeX Live. Nothing here touches the user's PATH.
Source: "..\build\cache\wheels-ce\*"; DestDir: "{tmp}\wheels-ce"; Components: ce; Flags: ignoreversion deleteafterinstall
Source: "requirements-ce.txt"; DestDir: "{app}\_setup"; Components: ce; Flags: ignoreversion
Source: "..\build\cache\texlive-lite\*"; DestDir: "{app}\texlive"; Components: ce; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "art\manimo.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
; double-click a project.mo file to open that project in Manimo (per user, no admin needed)
Root: HKCU; Subkey: "Software\Classes\.mo"; ValueType: string; ValueName: ""; ValueData: "Manimo.Project"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\Manimo.Project"; ValueType: string; ValueName: ""; ValueData: "Manimo project"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Manimo.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\manimo.ico"
Root: HKCU; Subkey: "Software\Classes\Manimo.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\python\pythonw.exe"" ""{app}\app\desktop.py"" ""%1"""
[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\desktop.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\manimo.ico"; AppUserModelID: "Manimo.App"; Comment: "{#AppSlogan}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\desktop.py"""; WorkingDir: "{app}\app"; IconFilename: "{app}\manimo.ico"; AppUserModelID: "Manimo.App"; Comment: "{#AppSlogan}"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\desktop.py"""; WorkingDir: "{app}\app"; Description: "Open {#AppName} now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Unregister the private Python that Setup added, before its files are deleted.
Filename: "{app}\_setup\python-installer.exe"; Parameters: "/uninstall /quiet"; RunOnceId: "RemovePrivatePython"; Flags: waituntilterminated runhidden

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  LogFile: string;

procedure Note(const S: string);
begin
  SaveStringToFile(LogFile, S + #13#10, True);
end;

procedure StopManimo(const Dir: string);
var
  Code: Integer;
begin
  // Close a running Manimo so its files can be replaced or removed.
  Exec('powershell.exe',
    '-NoProfile -ExecutionPolicy Bypass -Command "Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like ''' + Dir + '\*'' } | Stop-Process -Force"',
    '', SW_HIDE, ewWaitUntilTerminated, Code);
end;

function RunStep(const Exe, Params, Status: string): Boolean;
var
  Code: Integer;
begin
  WizardForm.StatusLabel.Caption := Status;
  WizardForm.FilenameLabel.Caption := '';
  Note('RUN ' + Exe + ' ' + Params);
  Result := Exec(Exe, Params, '', SW_HIDE, ewWaitUntilTerminated, Code);
  Note('  exit code ' + IntToStr(Code));
  if Result then Result := (Code = 0) or (Code = 3010);
end;

function PipCommand(const PyDir, Extra: string): string;
begin
  Result := '/C ""' + PyDir + '\python.exe" ' + Extra + ' >> "' + LogFile + '" 2>&1"';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Old: string;
  Code: Integer;
begin
  Result := '';
  StopManimo(ExpandConstant('{app}'));
  // Replace the earlier "ManimGX Studio" test build if it is still on this PC.
  Old := ExpandConstant('{localappdata}\ManimGX Studio');
  if (ExpandConstant('{param:KEEPOLD|0}') = '0') and FileExists(Old + '\Uninstall.ps1') then   // /KEEPOLD=1 skips this (for testing)
  begin
    StopManimo(Old);
    Exec('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -File "' + Old + '\Uninstall.ps1"', '', SW_HIDE, ewWaitUntilTerminated, Code);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  PyDir: string;
  Ok: Boolean;
begin
  if CurStep <> ssPostInstall then Exit;
  LogFile := ExpandConstant('{app}\install.log');
  DeleteFile(LogFile);
  PyDir := ExpandConstant('{app}\python');
  WizardForm.ProgressGauge.Style := npbstMarquee;
  Ok := True;

  if not FileExists(PyDir + '\python.exe') then
  begin
    Ok := RunStep(ExpandConstant('{app}\_setup\python-installer.exe'),
      '/quiet InstallAllUsers=0 TargetDir="' + PyDir + '" Include_launcher=0 Include_test=0 Include_doc=0 PrependPath=0 Shortcuts=0 AssociateFiles=0',
      'Setting up the engine room (one time only)...');
    // Python's own installer ignores TargetDir when it believes the same version is already installed somewhere
    // else (for example an older Manimo folder that was moved or deleted). Clear that registration and try once more.
    if Ok and not FileExists(PyDir + '\python.exe') then
    begin
      Note('python.exe missing after install; clearing the old registration and retrying');
      RunStep(ExpandConstant('{app}\_setup\python-installer.exe'), '/uninstall /quiet', 'Tidying up an older setup...');
      Ok := RunStep(ExpandConstant('{app}\_setup\python-installer.exe'),
        '/quiet InstallAllUsers=0 TargetDir="' + PyDir + '" Include_launcher=0 Include_test=0 Include_doc=0 PrependPath=0 Shortcuts=0 AssociateFiles=0',
        'Setting up the engine room (one time only)...');
    end;
    if Ok and not FileExists(PyDir + '\python.exe') then
    begin
      Note('python.exe is still missing');
      Ok := False;
    end;
  end;

  if Ok then
    Ok := RunStep(ExpandConstant('{cmd}'),
      PipCommand(PyDir, '-m pip install --no-index --find-links "' + ExpandConstant('{tmp}\wheels') + '" -r "' + ExpandConstant('{app}\app\requirements.txt') + '" --disable-pip-version-check'),
      'Installing the animation engine (the longest step)...');

  if Ok then
    Ok := RunStep(ExpandConstant('{cmd}'),
      PipCommand(PyDir, '-c "import manimgx as m; print(m.Scene)"'),
      'Checking that everything works...');

  // Optional component: Manim Community Edition from the bundled wheels (no network), then prove it and the bundled LaTeX start.
  if Ok and WizardIsComponentSelected('ce') then
  begin
    Ok := RunStep(ExpandConstant('{cmd}'),
      PipCommand(PyDir, '-m pip install --no-index --find-links "' + ExpandConstant('{tmp}\wheels-ce') + '" --find-links "' + ExpandConstant('{tmp}\wheels') + '" -r "' + ExpandConstant('{app}\_setup\requirements-ce.txt') + '" --disable-pip-version-check'),
      'Adding Manim Community Edition...');
    if Ok then
      Ok := RunStep(ExpandConstant('{cmd}'),
        PipCommand(PyDir, '-c "import manim; print(manim.__version__)"'),
        'Checking Manim Community Edition...');
    if Ok then
      Ok := RunStep(ExpandConstant('{cmd}'),
        '/C ""' + ExpandConstant('{app}\texlive\bin\windows\latex.exe') + '" --version >> "' + LogFile + '" 2>&1 && "' + ExpandConstant('{app}\texlive\bin\windows\dvisvgm.exe') + '" --version >> "' + LogFile + '" 2>&1"',
        'Checking LaTeX...');
  end
  else if Ok and DirExists(ExpandConstant('{app}\texlive')) then
  begin
    // The component was installed earlier and is now unticked: take away what it added (its Python packages and the TeX tree).
    RunStep(ExpandConstant('{cmd}'),
      PipCommand(PyDir, '-m pip uninstall -y manim manimpango pycairo scipy av moderngl moderngl-window glcontext mapbox-earcut pyglet pyglm pydub screeninfo srt tqdm watchdog beautifulsoup4 soupsieve cloup decorator audioop-lts --disable-pip-version-check'),
      'Removing Manim Community Edition...');
    DelTree(ExpandConstant('{app}\texlive'), True, True, True);
  end;

  WizardForm.ProgressGauge.Style := npbstNormal;
  if not Ok then
  begin
    MsgBox('Manimo could not finish setting itself up.' + #13#10#13#10 +
           'Nothing was changed outside the Manimo folder. A log was saved to:' + #13#10 + LogFile,
           mbError, MB_OK);
    Abort;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  StopManimo(ExpandConstant('{app}'));
  Result := True;
end;
