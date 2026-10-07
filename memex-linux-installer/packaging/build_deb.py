#!/usr/bin/env python3
"""Build the application .deb without root. Bundle pinned Curtin and its source."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2026.9.2~rc1'
sys.path.insert(0, str(ROOT / 'src'))
from memex_installer.version import PRODUCT_VERSION  # noqa: E402


def brand_version():
    return re.search(r'\d{4}\.\d{2}', PRODUCT_VERSION).group(0)


def fetch_curtin():
    lock = json.loads((ROOT / 'packaging/curtin.lock.json').read_text())
    cache = ROOT / 'vendor/curtin.tar.gz'
    cache.parent.mkdir(exist_ok=True)
    if not cache.exists():
        with urllib.request.urlopen(lock['url'], timeout=60) as src, cache.open('wb') as dest:
            shutil.copyfileobj(src, dest)
    if hashlib.sha256(cache.read_bytes()).hexdigest() != lock['sha256']:
        raise RuntimeError('Curtin source checksum mismatch. Remove the cached archive and retry.')
    return cache


def build(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    source_tar = fetch_curtin()
    with tempfile.TemporaryDirectory(prefix='memex-deb-') as td:
        staging = Path(td) / 'package'
        opt = staging / 'opt/memex-linux-installer'
        for directory in ('src', 'profiles', 'packaging', 'tests/fixtures'):
            shutil.copytree(ROOT / directory, opt / directory,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'mepc-logo-source.png', 'mepc-wordmark.png'))
        with tarfile.open(source_tar) as archive:
            archive.extractall(Path(td) / 'source', filter='data')
        upstream = next((Path(td) / 'source').iterdir())
        for directory in ('curtin', 'helpers', 'bin'):
            shutil.copytree(upstream / directory, opt / 'vendor' / directory)
        docs = staging / 'usr/share/doc/memex-installer'
        docs.mkdir(parents=True)
        shutil.copy2(source_tar, docs / 'curtin-source.tar.gz')
        shutil.copy2(upstream / 'LICENSE', docs / 'curtin-LICENSE')
        shutil.copy2(ROOT / 'packaging/curtin.lock.json', docs / 'curtin.lock.json')
        shutil.copy2(ROOT / 'README.md', docs / 'README.md')
        bin_dir = staging / 'usr/bin'
        bin_dir.mkdir(parents=True)
        for name, module in {'memex-wizard': 'memex_wizard.app', 'memex-engine': 'memex_engine.run',
                             'memex-completer': 'memex_completer.service',
                             'memex-completer-gui': 'memex_completer.gui', 'curtin': 'curtin'}.items():
            path = bin_dir / name
            path.write_text('#!/bin/sh\nexport PYTHONPATH=/opt/memex-linux-installer/src:/opt/memex-linux-installer/vendor\nexec /usr/bin/python3 -m ' + module + ' "$@"\n')
            path.chmod(0o755)
        copies = {
            'systemd/memex-setup.service': 'lib/systemd/system/memex-setup.service',
            'systemd/memex-live-kiosk.service': 'lib/systemd/system/memex-live-kiosk.service',
            'desktop/memex-setup.desktop': 'etc/xdg/autostart/memex-setup.desktop',
            'polkit/49-memex-setup.rules': 'etc/polkit-1/rules.d/49-memex-setup.rules',
            'bin/memex-kiosk': 'usr/libexec/memex-kiosk',
        }
        for source, destination in copies.items():
            dest = staging / destination
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / 'packaging' / source, dest)
        (staging / 'usr/libexec/memex-kiosk').chmod(0o755)
        # Display branding only; /etc/os-release stays untouched (apt, ubuntu-drivers, Docker rely on it).
        branding = {
            'kcm-about-distrorc': 'etc/xdg/kcm-about-distrorc',
            'memxos-logo.txt': 'usr/share/memxos/memxos-logo.txt',
            'memxos-logo-large.txt': 'usr/share/memxos/memxos-logo-large.txt',
            'memxos-logo.png': 'usr/share/memxos/memxos-logo.png',
        }
        for source, destination in branding.items():
            dest = staging / destination
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / 'packaging/branding' / source, dest)
        fastfetch = staging / 'etc/xdg/fastfetch/config.jsonc'
        fastfetch.parent.mkdir(parents=True, exist_ok=True)
        fastfetch.write_text((ROOT / 'packaging/branding/fastfetch/config.jsonc').read_text()
                             .replace('@MEMXOS_VERSION@', brand_version()))
        shutil.copytree(ROOT / 'packaging/kde/layout', staging / 'usr/share/plasma/look-and-feel/org.memex.desktop')
        xdg = staging / 'etc/xdg/kdeglobals'
        xdg.parent.mkdir(parents=True, exist_ok=True)
        xdg.write_text('[KDE]\nLookAndFeelPackage=org.memex.desktop\n')
        control = staging / 'DEBIAN'
        control.mkdir()
        (control / 'control').write_text(f'''Package: memex-installer
Version: {VERSION}
Architecture: all
Maintainer: Memory Express
Section: admin
Priority: optional
Conflicts: curtin-common, python3-curtin
Depends: python3 (>= 3.12), python3-yaml, python3-apt, python3-attr, python3-pyside6.qtwidgets, python3-pyudev, python3-debian, python3-oauthlib, python3-jsonschema, python3-packaging, python3-requests, openssl, rsync, gdisk, fdisk, parted, ntfs-3g, dosfstools, e2fsprogs, mtools, udev, efibootmgr, os-prober, ubuntu-drivers-common, pciutils, dbus-x11, xinit, xserver-xorg-core, xserver-xorg-input-all, xserver-xorg-video-all
Description: Memory Express Kubuntu installer and first-boot setup (release candidate)
 Includes a five-screen installer, pinned Curtin backend, and profile provisioning.
 Hardware installation validation is required before shop deployment.
''')
        destination = output / f'memex-installer_{VERSION}_all.deb'
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(staging), str(destination)], check=True)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    print(build(parser.parse_args().output))
