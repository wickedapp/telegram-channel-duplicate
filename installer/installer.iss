; Inno Setup Script for Telegram转发助手 (Telegram Forwarding Assistant)
;
; This script creates a Windows installer that:
; - Installs the application to Program Files
; - Creates desktop shortcut (optional)
; - Creates Start Menu entries
; - Supports full uninstallation
;
; Build requirements:
; - Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
; - PyInstaller output in dist/Telegram转发助手/
;
; Usage:
;   1. Run build_installer.py first to create the PyInstaller bundle
;   2. Open this file in Inno Setup Compiler
;   3. Build -> Compile (or press Ctrl+F9)

#define MyAppName "Telegram转发助手"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Telegram Channel Duplicator"
#define MyAppURL "https://github.com/telegram-channel-duplicator"
#define MyAppExeName "Telegram转发助手.exe"

[Setup]
; Application information
AppId={{E8F7A3B2-9C4D-5E6F-A1B2-C3D4E5F6A7B8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation directories
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

; Allow user to change install directory
DisableDirPage=no
DisableProgramGroupPage=no

; Output settings
OutputDir=..\dist
OutputBaseFilename=Telegram转发助手_Setup
SetupIconFile=assets\icon.ico

; Compression settings (solid compression for smaller installer)
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Installer appearance
WizardStyle=modern
WizardSizePercent=100

; Require administrator privileges for Program Files installation
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Uninstaller settings
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; Architecture - 64-bit only
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Minimum Windows version (Windows 10)
MinVersion=10.0

; Show license before installation (optional - uncomment if you have a license file)
; LicenseFile=..\LICENSE

; Version info for the installer executable
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} 安装程序
VersionInfoCopyright=Copyright (C) 2025
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
; Chinese (Simplified) as primary language
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
; English as fallback
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Desktop shortcut (optional, checked by default)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
; Quick Launch shortcut (optional)
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Auto-start with Windows (optional)
Name: "autostart"; Description: "开机自动启动"; GroupDescription: "系统设置:"; Flags: unchecked

[Files]
; Main application files from PyInstaller output
Source: "..\dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Template files for first-time setup
Source: "..\config.yaml.template"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\.env.template"; DestDir: "{app}"; Flags: ignoreversion

; Note: The following are already included in PyInstaller bundle, listed for documentation:
; - Telegram转发助手.exe (main executable)
; - All Python dependencies
; - assets/ folder with icons

[Dirs]
; Create data directory for logs and session files with user write permissions
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify

[Icons]
; Start Menu shortcuts
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "启动 Telegram 频道转发助手"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; Comment: "卸载 {#MyAppName}"

; Desktop shortcut (if selected)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "启动 Telegram 频道转发助手"

; Quick Launch shortcut (if selected)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

; Auto-start entry (if selected)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart; Comment: "Telegram 转发助手自动启动"

[Registry]
; Register application in Windows Apps
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletekey

; Store install path for application reference
Root: HKCU; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Run]
; Option to run application after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up user-created files on uninstall (optional)
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\config.yaml"
Type: files; Name: "{app}\.env"
Type: files; Name: "{app}\*.session"
Type: files; Name: "{app}\*.session-journal"

[Code]
// Pascal Script for custom installation logic

var
  ConfigPage: TInputQueryWizardPage;

// Called during initialization
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

// Check if application is running before installation/uninstallation
function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  // Use tasklist to check if the process is running
  Result := Exec('cmd.exe', '/c tasklist /FI "IMAGENAME eq {#MyAppExeName}" | find /i "{#MyAppExeName}"',
                 '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

// Prompt user to close application if running
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';

  if IsAppRunning() then
  begin
    if MsgBox('检测到 {#MyAppName} 正在运行。' + #13#10 + #13#10 +
              '请关闭程序后再继续安装。' + #13#10 + #13#10 +
              '点击"确定"重试，或点击"取消"退出安装。',
              mbConfirmation, MB_OKCANCEL) = IDOK then
    begin
      // User wants to retry - check again
      if IsAppRunning() then
        Result := '请先关闭 {#MyAppName} 再继续安装。';
    end
    else
    begin
      Result := '安装已取消。';
    end;
  end;
end;

// Initialize uninstall - check if app is running
function InitializeUninstall(): Boolean;
begin
  Result := True;

  if IsAppRunning() then
  begin
    MsgBox('检测到 {#MyAppName} 正在运行。' + #13#10 + #13#10 +
           '请先关闭程序再进行卸载。', mbError, MB_OK);
    Result := False;
  end;
end;

// Called after successful installation
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Copy template files if config doesn't exist
    if not FileExists(ExpandConstant('{app}\config.yaml')) then
    begin
      if FileExists(ExpandConstant('{app}\config.yaml.template')) then
        FileCopy(ExpandConstant('{app}\config.yaml.template'),
                 ExpandConstant('{app}\config.yaml'), False);
    end;

    if not FileExists(ExpandConstant('{app}\.env')) then
    begin
      if FileExists(ExpandConstant('{app}\.env.template')) then
        FileCopy(ExpandConstant('{app}\.env.template'),
                 ExpandConstant('{app}\.env'), False);
    end;
  end;
end;
