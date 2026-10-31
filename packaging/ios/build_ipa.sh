#!/bin/bash
# Build .ipa on macOS with Xcode CLI (for mobile WebView APK wrapper or native build)
set -e
VERSION=2.1.0
SCHEME="PegasusMobile"
# Export archive for device
xcodebuild -scheme "${SCHEME}" -archivePath /tmp/PegasusMobile.xcarchive archive 2>/dev/null || echo "Archive requires full Xcode project; using exported .app instead"
# If archive exists, export
if [ -d /tmp/PegasusMobile.xcarchive ]; then
  xcodebuild -exportArchive -archivePath /tmp/PegasusMobile.xcarchive -exportOptionsPlist ios/ExportOptions.plist -exportPath /tmp/export/
  cp /tmp/export/*.ipa ../Pegasus-Phantom-Menace-${VERSION}.ipa
  echo ".ipa created: ../Pegasus-Phantom-Menace-${VERSION}.ipa"
else
  echo "Build .ipa manually from mobile sources. See ios/export.sh"
fi
