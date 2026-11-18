/**
 * Pegasus Phantom Menace - NSIS installer custom script.
 *
 * Installed via electron-builder's nsis.include option. Adds:
 *   - "Launch at login" checkbox on the finish page
 *   - Optional desktop / start-menu shortcuts (already default in package.json)
 *   - Clean uninstall that removes the Run key and scheduled task
 */
!macro customInstall
  ; Register auto-start for the current user (HKCU Run key).
  ; electron-builder 24.x exposes the executable name as
  ; ${APP_EXECUTABLE_FILENAME}; ${APP_FILENAME_EXE} does not exist and
  ; makensis treats the unknown variable as a fatal warning.
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "PegasusPhantomMenace" "$INSTDIR\${APP_EXECUTABLE_FILENAME}"
  ; Record for uninstall.
  WriteRegStr HKCU "Software\${APP_FILENAME}" "InstallDir" "$INSTDIR"

  ; Bootstrap the external operator toolchain (ADB/platform-tools, cloudflared,
  ; scrcpy, jadx, apktool, ngrok, frida, nmap, Wireshark/tshark, Metasploit,
  ; ssh, socat) into ~/.pegasus/tools, using the latest release of each tool.
  ; Tools are added to the user PATH (HKCU Environment). Best-effort and
  ; never fatal: the log is ~/.pegasus/logs/tool_bootstrap.log and the console
  ; can retry from the tool page. Runs through both python launchers so it
  ; works whether or not `py` is registered on the machine.
  nsExec::ExecToLog '"$SYSDIR\cmd.exe" /C python "$INSTDIR\resources\tool_bootstrap.py" --all'
  nsExec::ExecToLog '"$SYSDIR\cmd.exe" /C py -3 "$INSTDIR\resources\tool_bootstrap.py" --all'
!macroend

!macro customUnInstall
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "PegasusPhantomMenace"
  DeleteRegValue HKCU "Software\${APP_FILENAME}" "InstallDir"
  ; Remove the scheduled-task fallback if it exists.
  nsExec::ExecToLog 'schtasks /delete /tn "PegasusPhantomMenace" /f'
!macroend

; NOTE: do NOT define customInstallMode here. electron-builder's assisted
; installer (used when oneClick=false) defines that macro itself and expects it
; to set "$(user_var: output)"; overriding it with a no-argument macro makes
; makensis abort with:
;   Error in macro customInstallMode on macroline 2
;   Usage: StrCpy $(user_var: output) str [maxlen] [startoffset]
; Install mode is already controlled from package.json
; ("oneClick": false, "perMachine": false).
