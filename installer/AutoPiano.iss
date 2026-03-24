#define AppName "AutoPiano"
#define AppVersion "2.1.0"
#define AppPublisher "Toastaspiring"
#define AppURL "https://github.com/Toastaspiring/AutoPiano"
#define SourceRoot ".."

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=AutoPiano-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
SetupIconFile=
UninstallDisplayName={#AppName}
MinVersion=10.0

; Custom wizard page colors (dark theme via WizardImageFile isn't possible in script,
; but we use a clean default Inno Setup modern style)

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; App source
Source: "{#SourceRoot}\ModernAutoPiano\*"; DestDir: "{app}\ModernAutoPiano"; Flags: recursesubdirs createallsubdirs ignoreversion
; MIDI folder (create empty if missing)
Source: "{#SourceRoot}\Midi\*"; DestDir: "{app}\Midi"; Flags: recursesubdirs createallsubdirs ignoreversion skipifsourcedoesntexist
; Launcher
Source: "{#SourceRoot}\AutoPiano.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\AutoPiano.bat"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\AutoPiano.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Install Python dependencies after copying files
Filename: "{cmd}"; Parameters: "/c pythonw --version >nul 2>&1 || (echo Python not found & pause)"; Flags: runhidden waituntilterminated
Filename: "{cmd}"; Parameters: "/c python -m pip install -r ""{app}\ModernAutoPiano\requirements.txt"" --quiet"; StatusMsg: "Installing Python dependencies (first run only)…"; Flags: runhidden waituntilterminated
; Optionally launch after install
Filename: "{app}\AutoPiano.bat"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent shellexec

[UninstallDelete]
; Clean up __pycache__ folders
Type: filesandordirs; Name: "{app}\ModernAutoPiano\src\__pycache__"
Type: filesandordirs; Name: "{app}\ModernAutoPiano\__pycache__"
