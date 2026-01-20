; PC Monitor Agent - Inno Setup Script
; Download Inno Setup from: https://jrsoftware.org/isdl.php

#define MyAppName "PC Monitor Agent"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "PC Monitor"
#define MyAppURL "https://github.com/mitchmode/pc-monitor"
#define MyAppExeName "pc-monitor-agent.exe"

[Setup]
AppId={{B2C3D4E5-F6A7-8901-BCDE-F12345678901}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\PC Monitor Agent
DefaultGroupName=PC Monitor
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=PCMonitorAgent-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start PC Monitor Agent automatically on Windows startup"; GroupDescription: "Startup Options:"

[Files]
Source: "..\dist\windows\pc-monitor-agent.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PCMonitorAgent"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ServerURLPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  ServerURLPage := CreateInputQueryPage(wpSelectTasks,
    'Server Configuration', 'Configure the PC Monitor Server connection',
    'Please enter the URL of your PC Monitor Server:');
  ServerURLPage.Add('Server URL:', False);
  ServerURLPage.Values[0] := 'http://YOUR_SERVER_IP:8000';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigFile: string;
  ServerURL: string;
begin
  if CurStep = ssPostInstall then
  begin
    ServerURL := ServerURLPage.Values[0];
    ConfigFile := ExpandConstant('{app}\agent-config.txt');
    SaveStringToFile(ConfigFile, 'SERVER_URL=' + ServerURL, False);
  end;
end;
