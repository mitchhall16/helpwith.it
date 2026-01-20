; PC Monitor Server - Inno Setup Script
; Download Inno Setup from: https://jrsoftware.org/isdl.php

#define MyAppName "PC Monitor Server"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "PC Monitor"
#define MyAppURL "https://github.com/mitchmode/pc-monitor"
#define MyAppExeName "pc-monitor-server.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\PC Monitor Server
DefaultGroupName=PC Monitor
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=PCMonitorServer-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start PC Monitor Server automatically on Windows startup"; GroupDescription: "Startup Options:"; Flags: unchecked

[Files]
Source: "..\dist\windows\pc-monitor-server.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\windows\config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "..\dashboard\*"; DestDir: "{app}\dashboard"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Open Dashboard"; Filename: "http://localhost:8000"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PCMonitorServer"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
Filename: "http://localhost:8000"; Description: "Open Dashboard in Browser"; Flags: postinstall shellexec skipifsilent unchecked

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Open firewall port
    Exec('netsh', 'advfirewall firewall add rule name="PC Monitor Server" dir=in action=allow protocol=tcp localport=8000', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
