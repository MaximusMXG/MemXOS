#!/usr/bin/env python3
"""Report build prerequisites without attempting privileged operations."""
import argparse
import json
import os
import platform
import shutil
from pathlib import Path

TOOLS = ['xorriso', 'unsquashfs', 'mksquashfs', 'chroot', 'mount', 'umount',
         'unshare', 'dpkg-deb', 'gpg', 'python3']


def inspect(workdir):
    cap = next((line.split()[1] for line in Path('/proc/self/status').read_text().splitlines()
                if line.startswith('CapEff:')), '0')
    mask = int(cap, 16)
    missing_caps = [name for bit, name in [(21, 'CAP_SYS_ADMIN'), (18, 'CAP_SYS_CHROOT'), (27, 'CAP_MKNOD')]
                    if not mask & (1 << bit)]
    missing = [name for name in TOOLS if shutil.which(name) is None]
    free = shutil.disk_usage(workdir).free // 1024**3
    errors = []
    if platform.machine() not in {'x86_64', 'amd64'}:
        errors.append('An amd64 Linux build host is required.')
    if os.geteuid() != 0:
        errors.append('Run the ISO build with sudo on the build host.')
    if missing_caps:
        errors.append('Missing capabilities: ' + ', '.join(missing_caps))
    if missing:
        errors.append('Missing tools: ' + ', '.join(missing))
    if free < 60:
        errors.append(f'At least 60 GiB free workspace is required; available: {free} GiB. Allocate an 80 GB or larger build disk.')
    return {'ready': not errors, 'architecture': platform.machine(), 'free_gib': free,
            'missing_tools': missing, 'missing_capabilities': missing_caps, 'errors': errors}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workdir', type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = inspect(args.workdir)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['ready'] else 2)
