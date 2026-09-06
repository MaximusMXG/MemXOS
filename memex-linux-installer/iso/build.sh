#!/usr/bin/env bash
# Scaffold for remixing Kubuntu LTS into the Memory Express installer ISO.
# This script prints the required steps until Cubic/live-build is wired on a build host.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Memex ISO build scaffold"
echo "Package root: $ROOT"
echo
echo "1. Place Kubuntu LTS ISO at iso/cache/kubuntu.iso"
echo "2. Open with Cubic (or live-build) and chroot into the live filesystem"
echo "3. Copy $ROOT/src to /opt/memex-linux-installer"
echo "4. Install PySide6 + PyYAML in the live environment"
echo "5. Install packaging/systemd and packaging/desktop units"
echo "6. Configure live session to autostart: python3 -m memex_wizard.app"
echo "7. Rebuild ISO as ME-Linux-\$(date +%Y.%m).1.iso"
echo
echo "See iso/README.md for details."
