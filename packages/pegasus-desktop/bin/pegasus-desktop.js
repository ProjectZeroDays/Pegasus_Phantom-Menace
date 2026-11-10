#!/usr/bin/env node
/**
 * pegasus-desktop - launch the Pegasus Phantom Menace desktop shell.
 *
 * Starts Electron on the packaged wrapper. The Electron main process boots the
 * Python backend (start_server.py / run_server.py) and points the window at it.
 */
'use strict';

const path = require('path');
const { spawn } = require('child_process');

const appDir = path.resolve(__dirname, '..');

function resolveElectron() {
  try {
    // electron is an optional peer - only present in a dev checkout.
    return require('electron');
  } catch (_) {
    return null;
  }
}

const electron = resolveElectron();
if (!electron) {
  console.error(
    'pegasus-desktop: electron is not installed in this project.\n' +
    'Install the Windows build from the release instead:\n' +
    '  https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace/releases',
  );
  process.exit(1);
}

const child = spawn(electron, [appDir], { stdio: 'inherit' });
child.on('close', (code) => process.exit(code == null ? 0 : code));
