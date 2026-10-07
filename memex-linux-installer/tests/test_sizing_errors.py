"""Shared sizing parity, ME-SPACE, hibernated detection and specific engine error codes."""
import json
import subprocess
from dataclasses import replace

import pytest

from memex_engine import backend
from memex_engine.preview import build_preview
from memex_engine.run import main
from memex_engine.storage import storage_config
from memex_installer.answers_io import save_answers
from memex_installer.errors import ErrorCode, MemexError
from memex_installer.models import LinuxSizePreset
from memex_installer.preflight import run_preflight
from memex_installer.sizing import GIB, MIB
from tests.test_storage_backend import answers, disk, parts


def linux_root(cfg):
    return next(c for c in cfg['config'] if c['id'] == 'linux-root')['size']


@pytest.mark.parametrize('preset', [LinuxSizePreset.GB_100, LinuxSizePreset.HALF, LinuxSizePreset.ALL_LEFTOVER])
def test_preflight_and_storage_agree(preset):
    a, d, p = answers(), disk(), parts()
    a = replace(a, linux_size=preset)
    win = p[2]
    res = run_preflight(a, [d], win_size=win.size, win_min=win.min_size)
    assert res.ok and not res.estimated
    cfg = storage_config(a, res.plan, d, p)
    assert linux_root(cfg) == res.plan.linux_size_bytes


def test_estimate_flagged_without_partitions():
    res = run_preflight(answers(), [disk()])
    assert res.ok and res.estimated


def test_space_when_ntfs_min_too_large():
    a, d, p = replace(answers(), linux_size=LinuxSizePreset.ALL_LEFTOVER), disk(), parts()
    win = replace(p[2], min_size=480 * GIB)
    res = run_preflight(a, [d], win_size=win.size, win_min=win.min_size)
    assert not res.ok and res.error == ErrorCode.SPACE
    plan = run_preflight(a, [d]).plan
    with pytest.raises(MemexError) as exc:
        storage_config(a, plan, d, [p[0], p[1], win, p[3]])
    assert exc.value.code == ErrorCode.SPACE


def test_preview_uses_inspection_and_blocks_on_space():
    a, d, p = replace(answers(), linux_size=LinuxSizePreset.ALL_LEFTOVER), disk(), parts()
    ok = build_preview(a, [d], lambda disk: p)
    assert ok['status'] == 'preview_ready' and ok['size_estimated'] is False
    big = [p[0], p[1], replace(p[2], min_size=480 * GIB), p[3]]
    assert build_preview(a, [d], lambda disk: big)['error']['code'] == 'ME-SPACE'
    assert build_preview(a, [d])['size_estimated'] is True


def fake_runner(ntfs):
    table = {'partitiontable': {'label': 'gpt', 'sectorsize': 512, 'partitions': [
        {'node': '/dev/x1', 'start': 2048, 'size': 10**9 // 512, 'type': 'EBD0A0A2-B9E5-4433-87C0-68B6B72699C7',
         'uuid': 'u1'}]}}

    def run(cmd):
        if cmd[0] == 'sfdisk':
            return json.dumps(table)
        if cmd[0] == 'lsblk':
            return json.dumps({'blockdevices': [{'name': '/dev/x1', 'fstype': 'ntfs'}]})
        if cmd[0] == 'ntfsls':
            return 'SYSTEM\nSOFTWARE\n'
        return ntfs(cmd)
    return run


def test_hibernated_called_process_error():
    def ntfs(cmd):
        raise subprocess.CalledProcessError(1, cmd, output='', stderr='Windows is hibernated, refused to mount')
    with pytest.raises(MemexError) as exc:
        backend.inspect_partitions(disk(), fake_runner(ntfs))
    assert exc.value.code == ErrorCode.HIBERNATED


def test_dirty_ntfs_output_without_error_exit():
    with pytest.raises(MemexError) as exc:
        backend.inspect_partitions(disk(), fake_runner(lambda c: 'Volume is scheduled for check. Run chkdsk /f'))
    assert exc.value.code == ErrorCode.HIBERNATED


def test_other_ntfs_failure_stays_generic():
    def ntfs(cmd):
        raise subprocess.CalledProcessError(1, cmd, stderr='some other failure')
    with pytest.raises(ValueError) as exc:
        backend.inspect_partitions(disk(), fake_runner(ntfs))
    assert not isinstance(exc.value, MemexError)


def test_preview_blocks_hibernated():
    def inspect(_disk):
        raise MemexError(ErrorCode.HIBERNATED)
    assert build_preview(answers(), [disk()], inspect)['error']['code'] == 'ME-WINDOWS-HIBERNATED'


def test_run_emits_specific_code(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'a.yaml'
    save_answers(path, answers())

    def boom(*args, **kwargs):
        raise MemexError(ErrorCode.HIBERNATED)
    monkeypatch.setattr('memex_engine.run.install', boom)
    assert main([str(path), '--install', '--confirm-disk', 'disk-1']) == 2
    err = json.loads(capsys.readouterr().err)
    assert err['error']['code'] == 'ME-WINDOWS-HIBERNATED'
    assert 'private-password' not in json.dumps(err)


def test_run_generic_error_stays_install_fail(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'a.yaml'
    save_answers(path, answers())
    monkeypatch.setattr('memex_engine.run.install', lambda *a, **k: (_ for _ in ()).throw(ValueError('private-password')))
    assert main([str(path), '--install', '--confirm-disk', 'disk-1']) == 2
    err = capsys.readouterr().err
    assert json.loads(err)['error']['code'] == 'ME-INSTALL-FAIL' and 'private-password' not in err
