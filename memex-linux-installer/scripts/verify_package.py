#!/usr/bin/env python3
"""Check packaged contents and import the bundled installer without installing it."""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('deb', type=Path)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='memex-package-check-') as td:
    root = Path(td)
    subprocess.run(['dpkg-deb', '-x', str(args.deb), td], check=True)
    required = ['usr/bin/memex-wizard', 'usr/bin/memex-engine', 'usr/bin/curtin',
                'usr/libexec/memex-kiosk', 'lib/systemd/system/memex-live-kiosk.service',
                'lib/systemd/system/memex-setup.service', 'etc/polkit-1/rules.d/49-memex-setup.rules',
                'usr/share/plasma/look-and-feel/org.memex.desktop/metadata.json',
                'usr/share/doc/memex-installer/curtin-source.tar.gz']
    for relative in required:
        if not (root / relative).is_file():
            raise RuntimeError('Package file missing: ' + relative)
    opt = root / 'opt/memex-linux-installer'
    env = {**os.environ, 'PYTHONPATH': str(opt / 'src') + ':' + str(opt / 'vendor')}
    subprocess.run([sys.executable, '-m', 'curtin', 'version'], env=env, check=True)
    subprocess.run([sys.executable, '-c', 'from memex_engine.backend import build_config; from memex_completer.service import run_completer'], env=env, check=True)
    print('Package contents and backend imports: passed')
