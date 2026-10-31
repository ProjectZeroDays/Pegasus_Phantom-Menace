#!/bin/bash
# Build .flatpak on Ubuntu VM: sudo apt install flatpak-builder
flatpak-builder --repo=repo build-dir org.projectzerodays.PegasusPhantomMenace.json
flatpak build-bundle repo ../Pegasus-Phantom-Menace-2.1.0.flatpak org.projectzerodays.PegasusPhantomMenace
echo ".flatpak created: ../Pegasus-Phantom-Menace-2.1.0.flatpak"
