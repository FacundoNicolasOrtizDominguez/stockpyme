; ============================================================================
; instalador.iss — Instalador de STOCKPYME (Inno Setup 6)
; Se compila con build_windows.ps1 (o abriendo este archivo en Inno Setup).
; Los datos del comercio (base, tickets, configuración) NO viven en la carpeta del
; programa sino en %LOCALAPPDATA%\StockPyME, así que desinstalar/actualizar no los borra.
; ============================================================================
#define AppName    "STOCKPYME"
#define AppVersion "1.0.0"
#define PuertoRed  "8765"

[Setup]
AppId={{B3A6E1F0-5C2D-4E8A-9F11-7A2D5B0C3E44}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Grupo 4 - Universidad del Aconcagua
DefaultDirName={autopf}\StockPyME
DefaultGroupName={#AppName}
OutputDir=instalador
OutputBaseFilename=StockPyME-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\StockPyME.exe

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"
; Solo para la PC que va a ser el servidor del comercio (si cambia el puerto en la app, ajustar la regla).
Name: "firewall"; Description: "Esta PC será el SERVIDOR: permitir que las otras cajas se conecten (abre el puerto {#PuertoRed} en el firewall)"; GroupDescription: "Red del comercio:"; Flags: unchecked

[Files]
Source: "dist\StockPyME\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\StockPyME.exe"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\StockPyME.exe"; Tasks: desktopicon

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""STOCKPYME servidor"" dir=in action=allow protocol=TCP localport={#PuertoRed} profile=private,domain"; Flags: runhidden; Tasks: firewall
Filename: "{app}\StockPyME.exe"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""STOCKPYME servidor"""; Flags: runhidden; RunOnceId: "QuitarReglaFirewall"
