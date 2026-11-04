; ScoreGDT (Praxis-Build) - Installer-Skript fuer Inno Setup
; Wird von der Bauanleitung (.github/workflows/build-windows.yml) aufgerufen.
; Pfade sind relativ zu diesem Ordner (installer\).

#define MyVersion GetEnv("SCOREGDT_VERSION")
#define MyBuild GetEnv("SCOREGDT_TAG")

[Setup]
AppId={{6E2B8C41-3F7A-4D19-9B52-A1C7E0D4F823}
AppName=ScoreGDT (Praxis-Build)
AppVersion={#MyBuild}
AppPublisher=Quellcode: Fabian Treusch (gdttools.de)
DefaultDirName=C:\GDT\ScoreGDT
DisableProgramGroupPage=yes
DefaultGroupName=ScoreGDT
OutputDir=..
OutputBaseFilename=ScoreGDT-{#MyVersion}-praxis-Setup
SetupIconFile=..\icons\program.ico
UninstallDisplayIcon={app}\scoregdt.exe
UninstallDisplayName=ScoreGDT (Praxis-Build)
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=yes

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem Desktop für alle Benutzer anlegen"
Name: "autoupdate"; Description: "Jede Nacht um 03:00 Uhr automatisch auf Updates prüfen und installieren"

[Dirs]
Name: "{app}"; Permissions: users-modify
Name: "{app}\log"; Permissions: users-modify
Name: "{app}\pdf"; Permissions: users-modify
Name: "{commonappdata}\scoregdt"; Permissions: users-modify; Flags: uninsneveruninstall

[InstallDelete]
; Von Hand angelegte Hilfsskripte aus der Einrichtungsphase entfernen
Type: files; Name: "{commonstartup}\gdt-ordner-pro-benutzer.cmd"
Type: files; Name: "{commonstartup}\gdt-austausch-pro-benutzer.cmd"
Type: files; Name: "{commonstartup}\scoregdt-config.cmd"

[Files]
Source: "..\dist\scoregdt\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{commonprograms}\ScoreGDT"; Filename: "{app}\scoregdt.exe"
Name: "{commonprograms}\ScoreGDT aktualisieren"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\ScoreGDT-Update.ps1"""; IconFilename: "{app}\scoregdt.exe"
Name: "{commondesktop}\ScoreGDT"; Filename: "{app}\scoregdt.exe"; Tasks: desktopicon
; Bei jeder Anmeldung die persoenlichen Austauschordner anlegen (unsichtbar)
Name: "{commonstartup}\ScoreGDT Ordner"; Filename: "powershell.exe"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{app}\ScoreGDT-Ordner.ps1"""; IconFilename: "{app}\scoregdt.exe"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\ScoreGDT-Update.ps1"" -AufgabeEinrichten"; Flags: runhidden; Tasks: autoupdate
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\ScoreGDT-Update.ps1"" -AufgabeEntfernen"; Flags: runhidden; Tasks: not autoupdate
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\ScoreGDT-Ordner.ps1"""; Flags: runhidden

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\ScoreGDT-Update.ps1"" -AufgabeEntfernen"; Flags: runhidden; RunOnceId: "ScoreGDTUpdateEntfernen"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\log"
Type: filesandordirs; Name: "{app}\pdf"
