; Inno Setup script for the tagged Windows release.
; Build with: iscc /DAppVersion=0.1.1 packaging/ChessCoach.iss
#ifndef AppVersion
#define AppVersion "0.0.0-dev"
#endif

#define AppName "Chess Coach"
#define AppPublisher "Chess Coach"
#define AppExeName "ChessCoach.exe"

[Setup]
AppId={{B1A4F0E8-7D52-4F9B-A4F7-2A6B2D6A3B11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\ChessCoach
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=..\dist\installer
OutputBaseFilename=ChessCoach-{#AppVersion}-windows-x64-setup
ArchitecturesInstallIn64BitMode=x64
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\ChessCoach\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Chess Coach"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Chess Coach"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Chess Coach"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; User data is deliberately outside {app}; uninstall never deletes games or settings.
