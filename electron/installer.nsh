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
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "PegasusPhantomMenace" "$INSTDIR\${APP_FILENAME_EXE}"
  ; Record for uninstall.
  WriteRegStr HKCU "Software\${APP_FILENAME}" "InstallDir" "$INSTDIR"
!macroend

!macro customUnInstall
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "PegasusPhantomMenace"
  DeleteRegValue HKCU "Software\${APP_FILENAME}" "InstallDir"
  ; Remove the scheduled-task fallback if it exists.
  nsExec::ExecToLog 'schtasks /delete /tn "PegasusPhantomMenace" /f'
!macroend

!macro customInstallMode
  ; Ask the user whether to install for all users or just this one.
  StrCpy $INSTALL_MODE_PER_ALL_USERS "0"
!macroend
