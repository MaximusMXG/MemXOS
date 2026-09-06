"""Regression tests for partition preservation, resize bounds and install guards."""
import json
from dataclasses import replace
from pathlib import Path
import pytest

from memex_engine.backend import build_config, install
from memex_engine.storage import Partition, storage_config, MIB, GIB, EFI_TYPE
from memex_installer.models import Answers, DiskInfo, InstallMode, Language, LinuxSizePreset, ProfileId
from memex_installer.preflight import run_preflight


def disk():
    return DiskInfo('disk-1', 'Test SSD', 512 * GIB, '/dev/nvme0n1', has_windows=True,
                    serial='disk-1', stable_path='/dev/disk/by-id/wwn-test')


def answers(mode=InstallMode.DUAL_BOOT):
    d = disk()
    return Answers(Language.EN, ProfileId.HOME, d.id, d.model, d.size_bytes, mode,
                   LinuxSizePreset.GB_100, 'Alex Customer', 'alex', 'private-password', 'alex-pc')


def parts():
    return [
        Partition(1, '/dev/nvme0n1p1', MIB, 512*MIB, EFI_TYPE, '11111111-1111-1111-1111-111111111111', 'vfat'),
        Partition(2, '/dev/nvme0n1p2', 513*MIB, 16*MIB, 'e3c9e316-0b5c-4db8-817d-f92df00215ae', '22222222-2222-2222-2222-222222222222'),
        Partition(3, '/dev/nvme0n1p3', 529*MIB, 500*GIB, 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7', '33333333-3333-3333-3333-333333333333', 'ntfs', True, 100*GIB),
        Partition(4, '/dev/nvme0n1p4', 529*MIB+500*GIB, GIB, 'de94bba4-06d1-4d40-a16a-bfd50179d6ac', '44444444-4444-4444-4444-444444444444', 'ntfs'),
    ]


def config(a=None, d=None, partition_list=None):
    a, d = a or answers(), d or disk()
    plan = run_preflight(a, [d]).plan
    return storage_config(a, plan, d, parts() if partition_list is None else partition_list)


def test_same_disk_preserves_every_existing_partition_and_efi():
    cfg = config()['config']
    before = parts()
    existing = [p for p in cfg if p['type'] == 'partition' and p.get('preserve')]
    assert {p['number'] for p in existing} == {p.number for p in before}
    assert not cfg[0].get('wipe')
    for p in before:
        entry = next(e for e in existing if e['number'] == p.number)
        assert entry['offset'] == p.offset and entry['uuid'] == p.uuid
        if not p.windows:
            assert entry['size'] == p.size
            assert not entry.get('resize')
    assert next(c for c in cfg if c['id'] == 'efi-format')['preserve'] is True
    root = next(c for c in cfg if c['id'] == 'linux-root')
    win = before[2]
    assert root['offset'] + root['size'] <= win.offset + win.size
    assert root['number'] not in {p.number for p in before}


def test_wipe_targets_only_one_explicit_stable_disk():
    cfg = config(answers(InstallMode.LINUX_ONLY))['config']
    drives = [c for c in cfg if c['type'] == 'disk']
    assert len(drives) == 1 and drives[0]['path'] == disk().stable_path
    assert drives[0]['preserve'] is False
    assert 'wipe' in drives[0]


@pytest.mark.parametrize('change', [{'mounted': True}, {'read_only': True}, {'stable_path': ''}, {'is_usb': True}])
def test_unsafe_target_rejected(change):
    a, d = answers(InstallMode.LINUX_ONLY), disk()
    plan = run_preflight(a, [d]).plan
    with pytest.raises(ValueError):
        storage_config(a, plan, replace(d, **change))


def test_unknown_or_too_large_ntfs_minimum_rejected():
    for limit in (None, 450*GIB):
        table = parts()
        table[2] = replace(table[2], min_size=limit)
        with pytest.raises(ValueError):
            config(partition_list=table)


def test_missing_recovery_table_or_multiple_windows_rejected():
    with pytest.raises(ValueError):
        config(partition_list=[])
    table = parts()
    table[3] = replace(table[3], windows=True, min_size=GIB)
    with pytest.raises(ValueError):
        config(partition_list=table)


def test_config_does_not_embed_credentials_or_auto_reboot():
    a, d = answers(), disk()
    cfg, account = build_config(a, run_preflight(a, [d]).plan, d, partitions=parts())
    assert 'private-password' not in json.dumps(cfg) + json.dumps(account)
    assert account['password_hash'].startswith('$6$')
    assert 'password_hash' not in json.dumps(cfg)
    assert cfg['install']['save_install_config'] is False
    assert not cfg.get('power_state')
    assert cfg['sources']['rootfs']['type'] == 'fsimage'


def test_real_install_refused_outside_live_iso(monkeypatch):
    monkeypatch.setattr('memex_engine.backend.live_available', lambda: False)
    monkeypatch.setattr('memex_engine.backend.subprocess.run', lambda *a, **k: pytest.fail('Command ran'))
    with pytest.raises(RuntimeError):
        install(answers(), 'disk-1')
