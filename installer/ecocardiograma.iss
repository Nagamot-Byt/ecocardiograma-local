; Script Inno Setup para Ecocardiograma Local.
; Compilar con ISCC.exe (Inno Setup 6):
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\ecocardiograma.iss
; Requiere haber construido primero el exe con PyInstaller:
;   venv\Scripts\python.exe -m PyInstaller ecocardiograma.spec --noconfirm --clean
;
; El instalador puede instalar Ollama (motor de IA local) de forma silenciosa
; al finalizar. La app lo inicia automaticamente y descarga el modelo la
; primera vez que se usa.

#define MyAppName "Ecocardiograma Local"
#define MyAppVersion "1.0.2"
#define MyAppExeName "EcocardiogramaLocal.exe"
#define MyAppPublisher "YAMID"
#define MyAppExeDir "..\dist\EcocardiogramaLocal"

[Setup]
AppId={{A8F3C2E1-4B6D-4E9A-9C31-YAMIDECO01}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\dist\installer
OutputBaseFilename=EcocardiogramaLocal-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"
Name: "installollama"; Description: "Instalar Ollama (motor de IA local, descarga ~700 MB)"; GroupDescription: "IA local (Ollama):"; Flags: checkedonce

[Files]
Source: "{#MyAppExeDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Descarga el instalador de Ollama solo si la tarea "installollama" esta marcada
Source: "https://ollama.com/download/OllamaSetup.exe"; DestName: "OllamaSetup.exe"; DestDir: "{tmp}"; \
  ExternalSize: 700_000_000; Flags: external download ignoreversion; Tasks: installollama

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  SetupPath: String;
  RetCode: Integer;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('installollama') then
  begin
    SetupPath := ExpandConstant('{tmp}\OllamaSetup.exe');
    if not FileExists(SetupPath) then
    begin
      MsgBox('No se pudo descargar Ollama. La IA local no estara disponible.' + #13#10 +
        'Puede instalarlo manualmente desde https://ollama.com', mbError, MB_OK);
    end
    else if not Exec(SetupPath, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-', '',
      SW_SHOWNORMAL, ewWaitUntilTerminated, RetCode) then
    begin
      MsgBox('Ollama no se instalo correctamente (codigo ' + IntToStr(RetCode) + ').',
        mbError, MB_OK);
    end;
  end;
end;
