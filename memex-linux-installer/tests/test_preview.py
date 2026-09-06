"""Exercise preview boundaries without access to a real disk."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from memex_engine.preview import build_preview
from memex_engine.run import main
from memex_installer.answers_io import save_answers
from memex_installer.disks import disks_from_snapshot
from memex_installer.models import Answers, InstallMode, Language, LinuxSizePreset, ProfileId

FIXTURES = Path(__file__).parent / 'fixtures'


def case(fixture='disks_dual_two.json', target_id='wwn-nvme-linux', mode=InstallMode.DUAL_BOOT):
    disks = disks_from_snapshot(json.loads((FIXTURES / fixture).read_text()))
    disk = next(d for d in disks if d.id == target_id)
    answers = Answers(Language.EN, ProfileId.HOME, disk.id, disk.model, disk.size_bytes,
                      mode, LinuxSizePreset.GB_100, 'Alex', 'alex', 'customer-secret', 'alex-pc')
    return answers, disks


@pytest.mark.parametrize('fixture,target,mode,status,code', [
    ('disks_linux_only.json', 'wwn-nvme0', InstallMode.LINUX_ONLY, 'preview_ready', None),
    ('disks_dual_two.json', 'wwn-nvme-linux', InstallMode.DUAL_BOOT, 'preview_ready', None),
    ('disks_dual_same.json', 'wwn-nvme0', InstallMode.DUAL_BOOT, 'preview_ready', None),
    ('disks_bitlocker.json', 'wwn-nvme0', InstallMode.DUAL_BOOT, 'blocked', 'ME-BITLOCKER'),
    ('disks_linux_only.json', 'wwn-nvme0', InstallMode.DUAL_BOOT, 'blocked', 'ME-NO-WINDOWS'),
    ('disks_linux_only.json', 'usb-installer', InstallMode.LINUX_ONLY, 'blocked', 'ME-USB-TARGET'),
])
def test_preview_matrix(fixture, target, mode, status, code, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Preview attempted to start an external command')
    monkeypatch.setattr('subprocess.run', forbidden)
    answers, disks = case(fixture, target, mode)
    report = build_preview(answers, disks)
    assert report['status'] == status
    assert report['installed'] is False and report['disk_changes'] is False
    assert 'customer-secret' not in json.dumps(report)
    if code:
        assert report['error']['code'] == code


@pytest.mark.parametrize('change', [{'model': 'Replacement SSD'}, {'size_bytes': 42}])
def test_disk_changed_since_confirmation(change):
    answers, disks = case()
    disks[1] = replace(disks[1], **change)
    assert build_preview(answers, disks)['error']['code'] == 'ME-DISK-GONE'


def test_removed_disk():
    answers, disks = case()
    assert build_preview(answers, disks[:1])['error']['code'] == 'ME-DISK-GONE'


def test_cli_blocks_old_destructive_switch(tmp_path, monkeypatch, capsys):
    answers, _ = case()
    path = tmp_path / 'answers.yaml'
    save_answers(path, answers)
    monkeypatch.setenv('MEMEX_DRY_RUN', '0')
    assert main([str(path), '--fixture', str(FIXTURES / 'disks_dual_two.json')]) == 2
    result = json.loads(capsys.readouterr().err)
    assert result['status'] == 'blocked'
    assert result['installed'] is False


def test_cli_preview_contains_no_credentials(tmp_path, capsys):
    answers, _ = case()
    path, output = tmp_path / 'answers.yaml', tmp_path / 'preview.json'
    save_answers(path, answers)
    assert main([str(path), '--fixture', str(FIXTURES / 'disks_dual_two.json'),
                 '--preview-out', str(output)]) == 0
    report = json.loads(output.read_text())
    assert report['warning']['code'] == 'ME-TWO-DISK'
    assert 'customer-secret' not in capsys.readouterr().out + output.read_text()


def test_seed_refuses_existing_system_directory(tmp_path, capsys):
    answers, _ = case()
    path = tmp_path / 'answers.yaml'
    save_answers(path, answers)
    root = tmp_path / 'root'
    root.mkdir()
    marker = root / 'existing'
    marker.write_text('keep')
    assert main([str(path), '--fixture', str(FIXTURES / 'disks_dual_two.json'),
                 '--seed-root', str(root)]) == 2
    assert marker.read_text() == 'keep'
    assert not (root / 'etc').exists()


def test_malformed_answers_do_not_disclose_input(tmp_path, capsys):
    path = tmp_path / 'answers.yaml'
    path.write_text('language: [customer-secret')
    assert main([str(path)]) == 2
    assert 'customer-secret' not in capsys.readouterr().err
