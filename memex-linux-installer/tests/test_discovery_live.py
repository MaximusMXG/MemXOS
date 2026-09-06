import json
import subprocess
from memex_installer.disks import discover_disks


def test_ntfs_data_disk_is_not_a_windows_install(monkeypatch):
    payload = {'blockdevices': [{'name': '/dev/sda', 'type': 'disk', 'model': 'SSD', 'size': 100000,
                               'serial': 'test', 'children': [{'name': '/dev/sda1', 'fstype': 'ntfs'}]}]}
    def runner(cmd):
        if cmd[0] == 'lsblk':
            return json.dumps(payload)
        raise subprocess.CalledProcessError(1, cmd)
    disks = discover_disks(runner)
    assert not disks[0].has_windows


def test_nested_mounted_partition_blocks_live_target(monkeypatch):
    payload = {'blockdevices': [{'name': '/dev/sda', 'type': 'disk', 'model': 'SSD', 'size': 100000,
                               'serial': 'test', 'children': [{'name': '/dev/sda1', 'fstype': 'ntfs',
                               'children': [{'name': '/dev/mapper/live', 'mountpoints': ['/']}]}]}]}
    disks = discover_disks(lambda cmd: json.dumps(payload) if cmd[0] == 'lsblk' else 'SYSTEM\nSOFTWARE\n')
    assert disks[0].has_windows
    assert disks[0].mounted
