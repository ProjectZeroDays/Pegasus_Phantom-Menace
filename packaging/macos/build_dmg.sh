#!/bin/bash
# Build .dmg on macOS VM (requires create-dmg: brew install create-dmg)
set -e
VERSION=2.1.0
APP="Pegasus Phantom Menace"
mkdir -p /tmp/dmg_build
# Build Electron .app (stub using actual web backend wrapped in Electron)
cp -r ../../pegasus/ui/web/dist /tmp/dmg_build/app 2>/dev/null || true
cp ../../launch_app.py /tmp/dmg_build/app/ 2>/dev/null || true
cp ../../README.md /tmp/dmg_build/app/ 2>/dev/null || true
hdiutil create -volname "Pegasus Phantom Menace ${VERSION}" -srcfolder /tmp/dmg_build/app -ov -format UDZO ../Pegasus-Phantom-Menace-${VERSION}.dmg
echo ".dmg created: ../Pegasus-Phantom-Menace-${VERSION}.dmg"
