"""Curtin installation backend; live-media and identity guards precede all writes."""
from __future__ import annotations
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path

import yaml
from memex_engine.storage import parse_table, storage_config
from memex_installer.disks import discover_disks, find_disk, windows_volume, _default_runner
from memex_installer.errors import ErrorCode, MemexError
from memex_installer.models import Answers, Language
from memex_installer.preflight import run_preflight
from memex_installer.secure_io import atomic_write, password_hash

MEDIA = Path('/cdrom/casper/filesystem.squashfs')
RUNTIME = Path('/run/memex-install')
MARKER = Path('/etc/memex/live-build.json')


def live_available() -> bool:
    return MARKER.is_file() and MEDIA.is_file() and 'boot=casper' in Path('/proc/cmdline').read_text().split()


def validate_live_host() -> None:
    if os.geteuid() != 0 or not live_available() or not Path('/sys/firmware/efi').is_dir():
        raise RuntimeError('Installation requires the MemXOS live ISO booted in UEFI mode as root.')
    for command in ('curtin', 'sfdisk', 'ntfsresize', 'ntfsls', 'openssl', 'udevadm'):
        if not shutil.which(command):
            raise RuntimeError(f'Required installation tool is missing: {command}')


def validate_account(answers: Answers) -> None:
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,30}', answers.username):
        raise ValueError('Username must start with a lowercase letter and use ASCII letters, numbers, _ or -.')
    if answers.username in {'root', 'daemon', 'nobody', 'ubuntu', 'kubuntu', 'memex'}:
        raise ValueError('This username is reserved.')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', answers.hostname):
        raise ValueError('Invalid hostname.')
    if not answers.display_name.strip() or any(c in answers.display_name for c in ':\n\r\x00'):
        raise ValueError('Invalid display name.')


def _hibernated(text: str) -> bool:
    """ntfsresize --info refuses hibernated / Fast Startup / dirty NTFS."""
    text = str(text).lower()
    return any(w in text for w in ('hibernat', 'unclean', 'inconsistent', 'chkdsk', 'dirty', 'fast restart'))


def windows_extent(partitions):
    """(size, resize minimum) of the single verified Windows NTFS volume, else (None, None)."""
    found = [p for p in partitions or [] if p.windows and p.fstype == 'ntfs' and p.min_size is not None]
    return (found[0].size, found[0].min_size) if len(found) == 1 else (None, None)


def checked_preflight(answers, disks, inspect=None):
    """Preflight using exact NTFS numbers (read-only inspection) when `inspect` is given.

    Returns (result, partitions); MemexError (e.g. hibernated Windows) propagates."""
    result = run_preflight(answers, disks)
    if inspect is None or not result.ok or result.plan is None or not result.plan.shrinks_windows:
        return result, None
    partitions = inspect(find_disk(disks, answers.target_disk_id))
    size, minimum = windows_extent(partitions)
    if size is None:
        return result, partitions  # storage_config validates the identity and fails closed
    return run_preflight(answers, disks, win_size=size, win_min=minimum), partitions


def inspect_partitions(disk, runner=_default_runner):
    table = json.loads(runner(['sfdisk', '--json', disk.device_path]))
    lsblk = json.loads(runner(['lsblk', '-J', '-p', '-o', 'NAME,FSTYPE', disk.device_path]))
    def visit(nodes):
        for node in nodes:
            yield node
            yield from visit(node.get('children') or [])
    filesystems = {n['name']: n.get('fstype') or '' for n in visit(lsblk['blockdevices'])}
    parts = parse_table(table, filesystems)
    validated = []
    for part in parts:
        if part.fstype == 'ntfs' and windows_volume(part.path, runner):
            # Without --force, dirty/hibernated/unsupported NTFS fails before any write.
            try:
                info = runner(['ntfsresize', '--info', '--no-progress-bar', part.path])
            except subprocess.CalledProcessError as exc:
                text = f'{exc.stdout or ""} {exc.stderr or ""} {exc.output or ""}'
                if _hibernated(text):
                    raise MemexError(ErrorCode.HIBERNATED) from None
                raise ValueError('NTFS minimum resize size could not be determined.') from None
            match = re.search(r'You might resize at (\d+) bytes', info)
            if not match:
                if _hibernated(info):
                    raise MemexError(ErrorCode.HIBERNATED)
                raise ValueError('NTFS minimum resize size could not be determined.')
            part = replace(part, windows=True, min_size=int(match.group(1)))
        validated.append(part)
    return validated


def build_config(answers, plan, disk, *, partitions=None, target=Path('/target'), runtime=RUNTIME):
    validate_account(answers)
    storage = storage_config(answers, plan, disk, partitions)
    metadata = {'profile': answers.profile.value, 'language': answers.language.value,
                'username': answers.username, 'display_name': answers.display_name,
                'hostname': answers.hostname, 'password_hash': password_hash(answers.password),
                'dual_boot': answers.mode.value == 'dual_boot'}
    # Account metadata is passed separately via a private tmpfs file, not embedded in Curtin logs.
    config = {
        'install': {'target': str(target), 'save_install_config': False,
                    'save_install_log': '/var/log/installer/curtin-install.log',
                    'log_file': '/var/log/memex-install/curtin.log',
                    'error_tarfile': None},
        'sources': {'rootfs': {'type': 'fsimage', 'uri': str(MEDIA)}},
        'storage': storage,
        'boot': {'bootloaders': ['grub'], 'update_nvram': True, 'reorder_uefi': False,
                 'remove_duplicate_entries': False, 'probe_additional_os': metadata['dual_boot']},
        'curthooks': {'mode': 'builtin'},
        'kernel': {'package': 'linux-generic'},
        'swap': {'filename': '/swap.img', 'size': '4G'},
        'late_commands': {
            '90-memex': ['/usr/bin/python3', '-m', 'memex_engine.finalize',
                          str(target), str(runtime / 'account.json')],
        },
    }
    return config, metadata


def install(answers: Answers, confirm_disk: str) -> int:
    validate_live_host()
    validate_account(answers)
    if confirm_disk != answers.target_disk_id:
        raise ValueError('Explicit target-disk confirmation is required.')
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    if RUNTIME.is_symlink() or RUNTIME.stat().st_uid != 0:
        raise RuntimeError('Unsafe runtime directory.')
    RUNTIME.chmod(0o700)
    import fcntl
    with (RUNTIME / 'install.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        disks = discover_disks()
        disk = find_disk(disks, answers.target_disk_id)
        result, partitions = checked_preflight(answers, disks, inspect_partitions)
        if not result.ok or result.plan is None:
            raise MemexError(result.error or ErrorCode.INSTALL_FAIL)
        if not disk or not stat.S_ISBLK(Path(disk.device_path).stat().st_mode):
            raise ValueError('Target is not a block device.')
        if str(Path(disk.stable_path).resolve()) != disk.device_path:
            raise ValueError('Stable disk path no longer matches the target.')
        config, account = build_config(answers, result.plan, disk, partitions=partitions)
        Path('/var/log/memex-install').mkdir(parents=True, exist_ok=True, mode=0o700)
        config_path, account_path = RUNTIME / 'curtin.yaml', RUNTIME / 'account.json'
        atomic_write(config_path, yaml.safe_dump(config))
        atomic_write(account_path, json.dumps(account))
        # Recheck identity and use immediately before Curtin's destructive boundary.
        refreshed = find_disk(discover_disks(), answers.target_disk_id)
        if refreshed != disk:
            raise ValueError('Disk state changed; restart the wizard.')
        try:
            with Path('/var/log/memex-install/engine.log').open('a') as log:
                process = subprocess.run(['curtin', '-c', str(config_path), 'install'],
                                         stdout=log, stderr=subprocess.STDOUT, timeout=7200,
                                         env={**os.environ, 'LC_ALL': 'C'})
            if process.returncode:
                raise RuntimeError('OS installation failed. See /var/log/memex-install/.')
            return 0
        finally:
            config_path.unlink(missing_ok=True)
            account_path.unlink(missing_ok=True)
