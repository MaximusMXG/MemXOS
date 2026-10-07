"""Explicit Curtin v2 GPT storage configuration; no implicit disk selection.

Reference: https://curtin.readthedocs.io/en/latest/topics/storage.html
Every existing partition is preserved in same-disk mode, including recovery/MSR.
"""
from dataclasses import dataclass
from pathlib import Path
import re

from memex_installer.errors import ErrorCode, MemexError
from memex_installer.models import Answers, DiskInfo, PartitionPlan
from memex_installer.sizing import GIB, MIB, MIN_LINUX, MIN_WINDOWS, linux_size_for, size_fits, windows_floor

EFI_TYPE = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'


@dataclass(frozen=True)
class Partition:
    number: int
    path: str
    offset: int
    size: int
    type_guid: str
    uuid: str
    fstype: str = ''
    windows: bool = False
    min_size: int | None = None


def parse_table(data: dict, filesystems: dict[str, str]) -> list[Partition]:
    table = data['partitiontable']
    if table.get('label') != 'gpt':
        raise ValueError('Same-disk installation requires GPT.')
    sector = int(table.get('sectorsize', 512))
    parts = []
    for p in table['partitions']:
        number = re.search(r'(\d+)$', p['node'])
        if not number or not p.get('uuid') or not p.get('type'):
            raise ValueError('Incomplete partition identity.')
        parts.append(Partition(int(number.group(1)), p['node'], int(p['start']) * sector,
                               int(p['size']) * sector, p['type'].lower(), p['uuid'],
                               filesystems.get(p['node'], '').lower()))
    if not parts or len({p.number for p in parts}) != len(parts):
        raise ValueError('Invalid partition table.')
    ordered = sorted(parts, key=lambda p: p.offset)
    if any(a.offset + a.size > b.offset for a, b in zip(ordered, ordered[1:])):
        raise ValueError('Overlapping partitions.')
    return ordered


def storage_config(answers: Answers, plan: PartitionPlan, disk: DiskInfo,
                   partitions: list[Partition] | None = None) -> dict:
    if (answers.target_disk_id != disk.id or plan.target_disk_id != disk.id
            or answers.target_disk_model != disk.model
            or answers.target_disk_size_bytes != disk.size_bytes):
        raise ValueError('The confirmed disk identity changed.')
    if disk.is_usb or disk.read_only or disk.mounted:
        raise ValueError('Target is USB, read-only, or in use.')
    if not disk.stable_path.startswith('/dev/disk/by-id/'):
        raise ValueError('A stable disk-by-id path is required.')
    if disk.size_bytes < MIN_LINUX + 1024 * MIB:
        raise ValueError('At least 41 GiB is required on the target.')
    drive = {'id': 'linux-disk', 'type': 'disk', 'path': disk.stable_path,
             'ptable': 'gpt', 'preserve': not plan.wipes_target}
    config = [drive]
    if plan.wipes_target:
        drive['wipe'] = 'superblock-recursive'
        config += [
            {'id': 'efi', 'type': 'partition', 'device': 'linux-disk', 'number': 1,
             'offset': MIB, 'size': 512 * MIB, 'flag': 'boot', 'grub_device': True},
            {'id': 'linux-root', 'type': 'partition', 'device': 'linux-disk', 'number': 2,
             'offset': 513 * MIB, 'size': (disk.size_bytes // MIB - 515) * MIB},
        ]
        preserve_efi = False
    else:
        if not plan.shrinks_windows or disk.bitlocker_on:
            raise ValueError('Unsupported same-disk layout or BitLocker is enabled.')
        parts = partitions or []
        candidates = [p for p in parts if p.windows and p.fstype == 'ntfs']
        esps = [p for p in parts if p.type_guid == EFI_TYPE and p.fstype in {'vfat', 'fat32'}]
        if len(candidates) != 1 or len(esps) != 1:
            raise ValueError('Exactly one verified Windows volume and one EFI partition are required.')
        win, esp = candidates[0], esps[0]
        if esp.size < 100 * MIB or win.min_size is None:
            raise ValueError('EFI capacity or NTFS resize limits could not be validated.')
        floor = windows_floor(win.min_size)
        linux_size = linux_size_for(answers.linux_size, win.size, win.min_size)
        if linux_size is None:
            raise ValueError('Select a Linux size for same-disk installation.')
        if not size_fits(linux_size, win.size, win.min_size):
            raise MemexError(ErrorCode.SPACE)
        # Keep the new root entirely within space freed from Windows; never move recovery partitions.
        new_end = ((win.offset + win.size - linux_size) // MIB) * MIB
        new_win_size = new_end - win.offset
        linux_size = ((win.offset + win.size - new_end) // MIB) * MIB
        if new_win_size < floor or linux_size < MIN_LINUX or new_win_size >= win.size:
            raise MemexError(ErrorCode.SPACE)
        for part in parts:
            entry = {'id': 'efi' if part == esp else f'existing-{part.number}',
                     'type': 'partition', 'device': 'linux-disk', 'number': part.number,
                     'offset': part.offset, 'size': part.size, 'preserve': True,
                     'partition_type': part.type_guid, 'uuid': part.uuid}
            if part == esp:
                entry.update(flag='boot', grub_device=True)
            if part == win:
                entry.update(resize=True, size=new_win_size)
            config.append(entry)
        used_numbers = {p.number for p in parts}
        number = next(n for n in range(1, 129) if n not in used_numbers)
        config.append({'id': 'linux-root', 'type': 'partition', 'device': 'linux-disk',
                       'number': number, 'offset': new_end, 'size': linux_size})
        preserve_efi = True
    config += [
        {'id': 'efi-format', 'type': 'format', 'volume': 'efi', 'fstype': 'fat32', 'preserve': preserve_efi},
        {'id': 'root-format', 'type': 'format', 'volume': 'linux-root', 'fstype': 'ext4'},
        {'id': 'root-mount', 'type': 'mount', 'device': 'root-format', 'path': '/'},
        {'id': 'efi-mount', 'type': 'mount', 'device': 'efi-format', 'path': '/boot/efi'},
    ]
    return {'version': 2, 'config': config}
