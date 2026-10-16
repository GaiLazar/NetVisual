; Script generated for NetVisual Official Windows Installer
; Author: Gai Lazar (gaipunkx+netvisual@gmail.com)

#define MyAppName "NetVisual A+"
#define MyAppVersion "6.0"
#define MyAppPublisher "Gai Lazar"
#define MyAppURL "https://github.com/gaipunkx/NetVisual"
#define MyAppExeName "NetVisual.exe"
#define MyAppContact "gaipunkx+netvisual@gmail.com"

[Setup]
AppId={{D37E84B1-6F82-4C10-91BA-8C53F693E1A2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppContact={#MyAppContact}
AppComments=NetVisual A+ Network Intelligence & Cyber Suite by Gai Lazar
DefaultDirName={autopf}\NetVisual
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist\installer
OutputBaseFilename=NetVisual-v6-Setup
SetupIconFile=NetVisual.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
VersionInfoVersion=6.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoCopyright=Copyright (C) 2026 Gai Lazar ({#MyAppContact})
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=6.0.0.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "hebrew"; MessagesFile: "compiler:Languages\Hebrew.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Run NetVisual automatically when Windows starts"; GroupDescription: "Windows Integration:"

[Files]
Source: "dist\NetVisual.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "NetVisual.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\NetVisual.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\NetVisual.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
