#!/usr/bin/env python3
"""Remix verified Kubuntu media in a private mount namespace; retain signed boot files."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from doctor import inspect
from download import download, verify, sha256

ROOT = Path(__file__).resolve().parents[1]


def run(*command, **kwargs):
    print('Running: ' + ' '.join(str(x) for x in command), flush=True)
    return subprocess.run([str(x) for x in command], check=True, **kwargs)


def build(args):
    work_parent = args.workdir.resolve()
    work_parent.mkdir(parents=True, exist_ok=True)
    report = inspect(work_parent)
    if not report['ready']:
        raise RuntimeError('\n'.join(report['errors']))
    if os.environ.get('MEMEX_PRIVATE_MOUNT_NAMESPACE') != '1':
        run('unshare', '--mount', '--propagation', 'private', 'env', 'MEMEX_PRIVATE_MOUNT_NAMESPACE=1',
            sys.executable, Path(__file__).resolve(), *sys.argv[1:])
        return
    cache = args.cache.resolve()
    base = args.base_iso.resolve() if args.base_iso else download(cache)
    base_hash = verify(base, cache)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output == base:
        raise RuntimeError('Output ISO already exists; choose a new output filename.')
    run(sys.executable, ROOT / 'packaging/build_deb.py', '--output', ROOT / 'dist')
    deb = ROOT / 'dist/memex-installer_2026.9.2~rc1_all.deb'
    # Keep work on failure for diagnosis; no automatic recursive deletion of an arbitrary user path.
    work = Path(tempfile.mkdtemp(prefix='memex-build-', dir=work_parent))
    root = work / 'rootfs'
    original = work / 'original.squashfs'
    mounts = []
    try:
        run('xorriso', '-osirrox', 'on', '-indev', base, '-extract', '/casper/filesystem.squashfs', original)
        run('unsquashfs', '-d', root, original)
        os_release = (root / 'etc/os-release').read_text()
        if 'VERSION_ID="26.04"' not in os_release:
            raise RuntimeError('The extracted image is not the pinned Ubuntu 26.04 release.')
        # Use the disk's existing package sources, enabling the required official components.
        for source in (root / 'etc/apt/sources.list.d').glob('*.sources'):
            text = source.read_text()
            import re
            text = re.sub(r'^Components:.*$', 'Components: main restricted universe multiverse', text, flags=re.M)
            source.write_text(text)
        policy = root / 'usr/sbin/policy-rc.d'
        old_policy = policy.read_bytes() if policy.exists() else None
        policy.write_text('#!/bin/sh\nexit 101\n')
        policy.chmod(0o755)
        resolv = root / 'etc/resolv.conf'
        old_resolv = ('link', os.readlink(resolv)) if resolv.is_symlink() else ('file', resolv.read_bytes() if resolv.exists() else b'')
        resolv.unlink(missing_ok=True)
        resolv.write_bytes(Path('/etc/resolv.conf').read_bytes())
        for source, destination, options in [
            ('/dev', 'dev', ['--rbind']), ('proc', 'proc', ['-t', 'proc']),
            ('sysfs', 'sys', ['-t', 'sysfs', '-o', 'ro']), ('tmpfs', 'run', ['-t', 'tmpfs'])]:
            dest = root / destination
            dest.mkdir(parents=True, exist_ok=True)
            run('mount', *options, source, dest)
            mounts.append(dest)
            if destination == 'dev':
                run('mount', '--make-rslave', dest)
        local_deb = root / 'tmp/memex-installer.deb'
        shutil.copy2(deb, local_deb)
        env = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive', 'LC_ALL': 'C'}
        run('chroot', root, 'apt-get', '-o', 'APT::Update::Error-Mode=any', 'update', env=env)
        run('chroot', root, 'apt-get', '-y', 'install', '/tmp/memex-installer.deb',
            'linux-generic', 'grub-efi-amd64-signed', 'shim-signed', 'mokutil', env=env)
        run('chroot', root, 'curtin', 'version', env=env)
        run('chroot', root, '/usr/bin/python3', '-c', 'from PySide6.QtWidgets import QApplication; import yaml', env=env)
        marker = root / 'etc/memex/live-build.json'
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({'version': '2026.09.2-RC1', 'base_sha256': base_hash, 'base': base.name}))
        # Enable kiosk only for casper boots, leave normal customer boots to SDDM.
        dropin = root / 'etc/systemd/system/sddm.service.d/memex-live.conf'
        dropin.parent.mkdir(parents=True, exist_ok=True)
        dropin.write_text('[Unit]\nConditionKernelCommandLine=!boot=casper\n')
        wants = root / 'etc/systemd/system/graphical.target.wants'
        wants.mkdir(parents=True, exist_ok=True)
        (wants / 'memex-live-kiosk.service').symlink_to('/lib/systemd/system/memex-live-kiosk.service')
        run('chroot', root, 'apt-get', 'clean', env=env)
        manifest = work / 'filesystem.manifest'
        with manifest.open('w') as stream:
            run('chroot', root, 'dpkg-query', '-W', '--showformat=${Package}\t${Version}\n', stdout=stream)
        local_deb.unlink()
        resolv.unlink(missing_ok=True)
        if old_resolv[0] == 'link':
            resolv.symlink_to(old_resolv[1])
        else:
            resolv.write_bytes(old_resolv[1])
        if old_policy is None:
            policy.unlink()
        else:
            policy.write_bytes(old_policy)
        for dest in reversed(mounts):
            run('umount', '-R', dest)
        mounts.clear()
        packed = work / 'filesystem.squashfs'
        run('mksquashfs', root, packed, '-noappend', '-comp', 'xz', '-processors', str(args.jobs))
        size_file = work / 'filesystem.size'
        size_file.write_text(subprocess.check_output(["du", "-sx", "--block-size=1", str(root)], text=True).split()[0] + "\n")
        # All boot image replay settings originate from the authenticated original ISO.
        # Do not replace vmlinuz, initrd, shim or GRUB. This preserves their signatures.
        partial = output.with_suffix('.iso.partial')
        # Rebuild the media-check list with hashes of replaced filesystem files.
        md5_list = work / 'md5sum.txt'
        run('xorriso', '-osirrox', 'on', '-indev', base, '-extract', '/md5sum.txt', md5_list)
        entries = {}
        for line in md5_list.read_text().splitlines():
            digest, filename = line.split(maxsplit=1)
            entries[filename.lstrip('*')] = digest
        for filename, path in [('casper/filesystem.squashfs', packed), ('casper/filesystem.manifest', manifest), ('casper/filesystem.size', size_file)]:
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'md5').hexdigest()
            for key in list(entries):
                if key.lstrip('./') == filename:
                    entries[key] = digest
        md5_list.write_text(''.join(f'{digest}  {filename}\n' for filename, digest in entries.items() if filename.lstrip('./') not in {'md5sum.txt', 'boot.catalog'}))
        # Single final mastering pass from the original avoids appending a second ISO session.
        run('xorriso', '-indev', base, '-outdev', partial, '-boot_image', 'any', 'replay',
            '-map', packed, '/casper/filesystem.squashfs', '-map', manifest, '/casper/filesystem.manifest',
            '-map', size_file, '/casper/filesystem.size', '-map', md5_list, '/md5sum.txt', '-commit', '-end')
        partial.rename(output)
        digest = sha256(output)
        output.with_suffix('.iso.sha256').write_text(digest + '  ' + output.name + '\n')
        output.with_suffix('.build.json').write_text(json.dumps({
            'version': '2026.09.2-RC1', 'built_at': datetime.now(timezone.utc).isoformat(),
            'base_sha256': base_hash, 'iso_sha256': digest, 'deb_sha256': sha256(deb),
            'validation': 'Built; VM and physical boot/install acceptance pending', 'workspace': str(work)
        }, indent=2) + '\n')
        print('ISO created: ' + str(output), flush=True)
    finally:
        for dest in reversed(mounts):
            subprocess.run(['umount', '-R', str(dest)], check=False)
        print('Build workspace retained: ' + str(work), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-iso', type=Path)
    parser.add_argument('--cache', type=Path, default=ROOT / 'iso/cache')
    parser.add_argument('--workdir', type=Path, default=ROOT / 'iso/work')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/ME-Linux-2026.09.2-RC1.iso')
    parser.add_argument('--jobs', type=int, default=4)
    try:
        build(parser.parse_args())
    except Exception as exc:
        print('Build stopped: ' + str(exc), file=sys.stderr)
        raise SystemExit(2)
