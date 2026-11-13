; Inno Setup script for Variety for Windows.
; Built by packaging\build.ps1, which passes the version: ISCC /DAppVersion=0.1.0 installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Variety for Windows"
#define AppExe "VarietyWin.exe"

[Setup]
AppId={{6E0B5C0E-6B0C-4C55-9E6B-5A1F3D2B7A41}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=mipawlus
AppPublisherURL=https://github.com/mipawlus/variety-win
DefaultDirName={autopf}\VarietyWin
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Installs for the current user only, so no administrator prompt is needed.
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\installer-output
OutputBaseFilename=VarietyWin-Setup-{#AppVersion}
SetupIconFile=..\src\varietywin\resources\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "autostart"; Description: "Start {#AppName} when I sign in to Windows"

[Files]
Source: "..\dist\VarietyWin\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"

[Registry]
; The same value the app's own "start at sign-in" setting reads and writes.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "VarietyWin"; ValueData: """{app}\{#AppExe}"""; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "VarietyWin"; \
    Flags: dontcreatekey uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Ask a running copy to exit so its files can be removed.
Filename: "{app}\{#AppExe}"; Parameters: "--quit"; RunOnceId: "QuitApp"; Flags: skipifdoesntexist

[Code]
// When upgrading, ask the running copy to exit before its files are replaced.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  Exe: String;
begin
  Result := '';
  Exe := ExpandConstant('{app}\{#AppExe}');
  if FileExists(Exe) then
  begin
    Exec(Exe, '--quit', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1500);
  end;
end;
