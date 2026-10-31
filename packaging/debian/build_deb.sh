#!/bin/bash
# Build .deb on Ubuntu/Debian VM — install: sudo apt install build-essential debhelper fakeroot
set -e
VERSION=2.1.0
NAME=Pegasus-Phantom-Menace
mkdir -p ../debian/DEBIAN
cp control ../debian/DEBIAN/control
# Copy installed files from repo root
mkdir -p ../debian/usr/lib/pegasus/../debian/usr/share/pegasus
cp -r ../../pegasus/ui/web/dist ../debian/usr/share/pegasus/ 2>/dev/null || true
cp -r ../../assets ../debian/usr/share/pegasus/ 2>/dev/null || true
cp ../../launch_app.py ../debian/usr/lib/pegasus/ 2>/dev/null || true
cp ../../README.md ../debian/usr/share/pegasus/ 2>/dev/null || true
dpkg-deb --build ../debian ../Pegasus-Phantom-Menace_${VERSION}_amd64.deb
echo ".deb created: ../Pegasus-Phantom-Menace_${VERSION}_amd64.deb"
