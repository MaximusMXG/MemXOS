"""Read-only disk inventory and conservative Windows detection."""
from __future__ import annotations
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from memex_installer.models import DiskInfo

Runner = Callable[[list[str]], str]


def _default_runner(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30).stdout


def disks_from_snapshot(data: dict[str, Any]) -> list[DiskInfo]:
    return [DiskInfo(**item) for item in data.get('disks', [])]


def _children(device: dict):
    for child in device.get('children') or []:
        yield child
        yield from _children(child)


def _stable_path(device: str) -> str:
    candidates = []
    for entry in Path('/dev/disk/by-id').glob('*'):
        if '-part' not in entry.name and str(entry.resolve()) == device:
            candidates.append(entry)
    candidates.sort(key=lambda p: (not p.name.startswith('wwn-'), p.name))
    return str(candidates[0]) if candidates else ''


def windows_volume(path: str, runner: Runner | None = None) -> bool:
    """ntfsls reads NTFS without mounting it or replaying a journal."""
    try:
        text = (runner or _default_runner)(['ntfsls', '-p', '/Windows/System32/config', path])
        names = {line.strip().upper() for line in text.splitlines()}
        return {'SYSTEM', 'SOFTWARE'}.issubset(names)
    except (OSError, subprocess.SubprocessError):
        return False


def discover_disks(runner: Runner | None = None) -> list[DiskInfo]:
    run = runner or _default_runner
    data = json.loads(run(['lsblk', '-J', '-b', '-p', '-o',
                          'NAME,SIZE,MODEL,TRAN,TYPE,FSTYPE,MOUNTPOINTS,SERIAL,WWN,RO,RM']))
    disks = []
    for device in data.get('blockdevices', []):
        if device.get('type') != 'disk':
            continue
        children = list(_children(device))
        nodes = [device, *children]
        encrypted = any((n.get('fstype') or '').lower() in {'bitlocker', 'fve-fs'} for n in nodes)
        windows = any((n.get('fstype') or '').lower() == 'ntfs' and windows_volume(n['name'], run) for n in nodes)
        if encrypted:
            for child in children:
                if (child.get('fstype') or '').lower() in {'vfat', 'fat32'}:
                    try:
                        run(['mdir', '-i', child['name'], '::/EFI/Microsoft/Boot/bootmgfw.efi'])
                        windows = True
                    except (OSError, subprocess.SubprocessError):
                        pass
        name = device['name']
        mounts = [m for n in nodes for m in (n.get('mountpoints') or []) if m]
        disks.append(DiskInfo(
            id=str(device.get('wwn') or device.get('serial') or name),
            model=(device.get('model') or 'Unknown').strip(), size_bytes=int(device['size']),
            device_path=name, is_usb=(device.get('tran') or '').lower() == 'usb' or '/cdrom' in mounts,
            has_windows=windows, bitlocker_on=encrypted, serial=(device.get('serial') or '').strip(),
            wwn=(device.get('wwn') or '').strip(), read_only=bool(device.get('ro')),
            mounted=bool(mounts), stable_path=_stable_path(name),
        ))
    return disks


def find_disk(disks: list[DiskInfo], disk_id: str) -> DiskInfo | None:
    matches = [d for d in disks if disk_id in {d.id, d.device_path}]
    return matches[0] if len(matches) == 1 else None
