#!/bin/bash
# Build .snap on Ubuntu VM: sudo apt install snapcraft
snapcraft clean
snapcraft
cp *.snap ../Pegasus-Phantom-Menace_2.1.0_amd64.snap || cp *.snap ../Pegasus-Phantom-Menace-2.1.0_amd64.snap
echo ".snap created"
