; Pegasus Phantom Menace v2 - NSIS installer
; Build: makensis /DOUTPUT=Pegasus-v2.0-Setup.exe electron\installer.nsi
;
; Components:
;   Core files (required), Windows Service (NSSM), Scheduled Task (fallback),
;   CLI PATH entry, desktop and Start Menu shortcuts.
;
; The service and task options are mutually exclusive; if both are selected the
; scheduled task is skipped.

!define APP_NAME "Pegasus Phantom Menace v2"
!define APP_VERSION "2.0.0"
!define APP_PUBLISHER "ProjectZeroDays"
!define APP_REGKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\PegasusPhantomMenace"
!define SERVICE_NAME "PegasusDaemon"
!define TASK_NAME "PegasusDaemon"

!ifndef OUTPUT
  !define OUTPUT "Pegasus-v2.0-Setup.exe"
!endif

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"
!include "x64.nsh"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "${OUTPUT}"
InstallDir "$PROGRAMFILES64\${APP_NAME}"
InstallDirRegKey HKLM "${APP_REGKEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
Unicode true
BrandingText "${APP_PUBLISHER}"

!define MUI_ABORTWARNING
!define MUI_ICON "..\..\..\..\pegasus.ico"
!define MUI_UNICON "..\..\..\..\pegasus.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\..\..\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Var PythonExe

Function .onInit
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONEXCLAMATION "Windows 10 or newer is required."
    Abort
  ${EndIf}
  ${If} ${RunningX64}
    SetRegView 64
  ${EndIf}

  ; Locate a real Python 3 interpreter.
  ReadRegStr $PythonExe HKLM "Software\Python\PythonCore\3.12\InstallPath" ""
  ${If} $PythonExe == ""
    ReadRegStr $PythonExe HKLM "Software\Python\PythonCore\3.11\InstallPath" ""
  ${EndIf}
  ${If} $PythonExe == ""
    nsExec::ExecToStack 'cmd /c where python'
    Pop $0
    Pop $PythonExe
  ${EndIf}
  ${If} $PythonExe == ""
    MessageBox MB_ICONEXCLAMATION "Python 3.11+ was not found on PATH.$\r$\nInstall Python, tick 'Add to PATH', then rerun setup."
    Abort
  ${EndIf}
  StrCpy $PythonExe "$PythonExe\python.exe"
  ${IfNot} ${FileExists} "$PythonExe"
    StrCpy $PythonExe "python.exe"
  ${EndIf}
FunctionEnd

Function .onSelChange
  ${If} ${SectionIsSelected} 2
  ${AndIf} ${SectionIsSelected} 3
    SectionSetFlags 3 0
  ${EndIf}
FunctionEnd

Section "Application files" SEC_CORE
  SectionIn RO
  SetOutPath "$INSTDIR"
  SetOverwrite on

  File /r /x node_modules /x __pycache__ /x .pytest_cache /x build /x dist "..\..\..\..\pegasus"
  File "..\..\..\..\run_pegasus.bat"
  File "..\..\..\..\requirements.txt"
  File "..\..\..\..\version.txt"
  File "..\..\..\..\LICENSE"
  File "..\daemon\install.ps1"
  File "..\daemon\uninstall.ps1"

  ; Isolated virtual environment.
  nsExec::ExecToLog '"$PythonExe" -m venv "$INSTDIR\.venv"'
  Pop $0
  ${If} ${FileExists} "$INSTDIR\.venv\Scripts\python.exe"
    nsExec::ExecToLog '"$INSTDIR\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-warn-script-location -r "$INSTDIR\requirements.txt"'
    Pop $0
  ${Else}
    DetailPrint "venv creation failed; falling back to the system interpreter."
    nsExec::ExecToLog '"$PythonExe" -m pip install --disable-pip-version-check --no-warn-script-location -r "$INSTDIR\requirements.txt"'
    Pop $0
  ${EndIf}

  CreateDirectory "$INSTDIR\launchers"
  FileOpen $0 "$INSTDIR\launchers\pegasus.bat" w
  FileWrite $0 "@echo off$\r$\n"
  FileWrite $0 "set PEGASUS_HOME=$INSTDIR$\r$\n"
  FileWrite $0 "if exist $\"$INSTDIR\.venv\Scripts\python.exe$\" ($\r$\n"
  FileWrite $0 "  $\"$INSTDIR\.venv\Scripts\python.exe$\" -m pegasus.core %*$\r$\n"
  FileWrite $0 ") else ($\r$\n"
  FileWrite $0 "  $\"$PythonExe$\" -m pegasus.core %*$\r$\n"
  FileWrite $0 ")$\r$\n"
  FileClose $0

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Pegasus CLI.lnk" "$INSTDIR\launchers\pegasus.bat" "" "" 0 SW_SHOWNORMAL
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Dashboard.lnk" "$INSTDIR\launchers\pegasus.bat" "dashboard" "" 0 SW_SHOWNORMAL
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

  WriteRegStr HKLM "${APP_REGKEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "${APP_REGKEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${APP_REGKEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "${APP_REGKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${APP_REGKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKLM "${APP_REGKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${APP_REGKEY}" "NoRepair" 1

  ${If} ${SectionIsSelected} 4
    nsExec::ExecToLog 'powershell -NoProfile -Command "$$p=[Environment]::GetEnvironmentVariable(\"Path\",\"Machine\"); if ($$p -notlike \"*$INSTDIR\launchers*\") { [Environment]::SetEnvironmentVariable(\"Path\", $$p + \";$INSTDIR\launchers\", \"Machine\") }"'
    Pop $0
  ${EndIf}
SectionEnd

Section "Windows service (auto-start)" SEC_SERVICE
  DetailPrint "Registering service ${SERVICE_NAME}..."
  nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\daemon\install.ps1" -InstallPath "$INSTDIR" -ServiceName "${SERVICE_NAME}"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONEXCLAMATION "Service registration failed (exit $0).$\r$\nInstall NSSM (https://nssm.cc) or choose the scheduled task component."
  ${EndIf}
SectionEnd

Section "Scheduled task (no NSSM needed)" SEC_TASK
  DetailPrint "Registering scheduled task ${TASK_NAME}..."
  nsExec::ExecToLog 'schtasks /Create /TN "${TASK_NAME}" /SC ONSTART /RL HIGHEST /TR "$\"$INSTDIR\launchers\pegasus.bat$\" daemon run" /F'
  Pop $0
  nsExec::ExecToLog 'schtasks /Run /TN "${TASK_NAME}"'
  Pop $0
SectionEnd

Section "Add to PATH" SEC_PATH
  ; Handled inside SEC_CORE once the launcher exists.
SectionEnd

Section "Desktop shortcut" SEC_DESKTOP
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\launchers\pegasus.bat" "" "" 0 SW_SHOWNORMAL
SectionEnd

Section "Uninstall"
  nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\daemon\uninstall.ps1" -ServiceName "${SERVICE_NAME}"'
  nsExec::ExecToLog 'schtasks /Delete /TN "${TASK_NAME}" /F'

  Delete "$DESKTOP\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Pegasus CLI.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Dashboard.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"

  nsExec::ExecToLog 'powershell -NoProfile -Command "$$p=[Environment]::GetEnvironmentVariable(\"Path\",\"Machine\"); if ($$p -like \"*$INSTDIR\launchers*\") { [Environment]::SetEnvironmentVariable(\"Path\", ($$p -replace [regex]::Escape(\";$INSTDIR\launchers\"), \"\"), \"Machine\") }"'

  RMDir /r "$INSTDIR\pegasus"
  RMDir /r "$INSTDIR\.venv"
  RMDir /r "$INSTDIR\launchers"
  Delete "$INSTDIR\requirements.txt"
  Delete "$INSTDIR\version.txt"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\run_pegasus.bat"
  Delete "$INSTDIR\daemon\install.ps1"
  Delete "$INSTDIR\daemon\uninstall.ps1"
  RMDir "$INSTDIR\daemon"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"

  DeleteRegKey HKLM "${APP_REGKEY}"
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_CORE} "Pegasus Phantom Menace application, virtual environment and launchers."
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_SERVICE} "Install the dashboard as a Windows service that starts at boot (requires NSSM)."
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_TASK} "Register a boot-time scheduled task instead of a service."
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_PATH} "Add the pegasus launcher to the machine PATH."
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_DESKTOP} "Create a desktop shortcut."
!insertmacro MUI_FUNCTION_DESCRIPTION_END
