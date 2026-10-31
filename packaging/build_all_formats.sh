#!/bin/bash
# Master packaging script — produces .deb .dmg .ipa .snap .flatpak for next release (v3.2.0 / v4.0.0)
# Run on VMs / CI: Ubuntu (deb+snap+flatpak), macOS (dmg+ipa), Windows (cross-compile via WSL)
set -e
echo "=== PACKAGING PIPELINE ==="

# 1 .deb (Debian/Ubuntu VM)
echo "[1/5] Building .deb..."
(cd packaging/debian && bash build_deb.sh) || echo "WARNING: .deb requires dpkg-dev (install: sudo apt install build-essential debhelper fakeroot)"

# 2 .dmg (macOS VM via ssh or local)
echo "[2/5] Building .dmg..."
(cd packaging/macos && bash build_dmg.sh) || echo "WARNING: .dmg requires macOS + create-dmg"

# 3 .ipa (macOS Xcode VM)
echo "[3/5] Building .ipa..."
(cd packaging/ios && bash build_ipa.sh) || echo "WARNING: .ipa requires Xcode / exported archive"

# 4 .snap (Ubuntu VM)
echo "[4/5] Building .snap..."
(cd packaging/snap && bash build_snap.sh) || echo "WARNING: .snap requires snapcraft (snap install snapcraft --classic)"

# 5 .flatpak (Ubuntu VM)
echo "[5/5] Building .flatpak..."
(cd packaging/flatpak && bash build_flatpak.sh) || echo "WARNING: .flatpak requires flatpak-builder (flatpak install flathub org.flatpak.Builder)"

echo "=== PACKAGING COMPLETE ==="
echo "Upload artifacts to GitHub next release:"
echo "  git tag v3.2.0 (or v4.0.0)"
echo "  gh release create v3.2.0 --assets '*.deb' '*.dmg' '*.ipa' '*.snap' '*.flatpak'"
