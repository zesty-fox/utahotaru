#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{5F81A445-2B4B-4FE7-87DB-6CF285BEEA89}
AppName=StrangeUtaGame
AppVersion={#AppVersion}
AppPublisher=Karaoke Studio
AppPublisherURL=https://github.com/karaoke-studio/StrangeUtaGame
DefaultDirName={localappdata}\Programs\StrangeUtaGame
DefaultGroupName=StrangeUtaGame
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\release
OutputBaseFilename=StrangeUtaGame-{#AppVersion}-windows-x86_64
SetupIconFile=..\..\src\strange_uta_game\resource\icon.ico
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\StrangeUtaGame.exe
ChangesAssociations=yes

[Files]
Source: "..\..\dist\StrangeUtaGame\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\StrangeUtaGame"; Filename: "{app}\StrangeUtaGame.exe"
Name: "{autodesktop}\StrangeUtaGame"; Filename: "{app}\StrangeUtaGame.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Registry]
Root: HKCU; Subkey: "Software\Classes\.sug"; ValueType: string; ValueName: ""; ValueData: "StrangeUtaGame.Project"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\StrangeUtaGame.Project"; ValueType: string; ValueName: ""; ValueData: "StrangeUtaGame Project"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\StrangeUtaGame.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\StrangeUtaGame.exe,0"
Root: HKCU; Subkey: "Software\Classes\StrangeUtaGame.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\StrangeUtaGame.exe"" ""%1"""

[Run]
Filename: "{app}\StrangeUtaGame.exe"; Description: "Launch StrangeUtaGame"; Flags: nowait postinstall skipifsilent
