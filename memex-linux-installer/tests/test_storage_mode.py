import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from memex_installer.disks import detect_storage_mode, disks_from_snapshot, storage_mode_from_snapshot
from memex_installer.errors import ErrorCode, error_message
from memex_installer.models import Answers, InstallMode, Language, LinuxSizePreset, ProfileId
from memex_installer.preflight import run_preflight

FIX = Path(__file__).parent / 'fixtures'


def pci(root, addr, vendor, device, cls):
    d = root / 'bus/pci/devices' / addr
    d.mkdir(parents=True)
    (d / 'vendor').write_text(f'0x{vendor:04x}\n')
    (d / 'device').write_text(f'0x{device:04x}\n')
    (d / 'class').write_text(f'0x{cls:06x}\n')


def test_ahci_is_none(tmp_path):
    pci(tmp_path, '0000:00:17.0', 0x8086, 0xa352, 0x010601)
    pci(tmp_path, '0000:01:00.0', 0x144d, 0xa808, 0x010802)
    assert detect_storage_mode(tmp_path) is None


def test_vmd_driver_bound(tmp_path):
    (tmp_path / 'bus/pci/drivers/vmd').mkdir(parents=True)
    (tmp_path / 'bus/pci/drivers/vmd/0000:00:0e.0').symlink_to(tmp_path)
    assert detect_storage_mode(tmp_path) == 'vmd'


def test_vmd_driver_without_devices(tmp_path):
    (tmp_path / 'bus/pci/drivers/vmd').mkdir(parents=True)
    (tmp_path / 'bus/pci/devices').mkdir(parents=True)
    (tmp_path / 'bus/pci/drivers/vmd/bind').write_text('')
    assert detect_storage_mode(tmp_path) is None


def test_vmd_device_id(tmp_path):
    pci(tmp_path, '0000:00:0e.0', 0x8086, 0x9a0b, 0x010400)
    assert detect_storage_mode(tmp_path) == 'vmd'


def test_vmd_id_wrong_vendor_ignored(tmp_path):
    pci(tmp_path, '0000:00:0e.0', 0x1022, 0x9a0b, 0x060000)
    assert detect_storage_mode(tmp_path) is None


def test_intel_sata_raid_class(tmp_path):
    pci(tmp_path, '0000:00:17.0', 0x8086, 0x2822, 0x010400)
    assert detect_storage_mode(tmp_path) == 'intel_raid'


def test_non_intel_raid_ignored(tmp_path):
    pci(tmp_path, '0000:03:00.0', 0x1000, 0x005f, 0x010400)
    assert detect_storage_mode(tmp_path) is None


def test_unreadable_never_raises(tmp_path):
    assert detect_storage_mode(tmp_path / 'missing') is None
    pci(tmp_path, '0000:00:17.0', 0x8086, 0x2822, 0x010400)
    (tmp_path / 'bus/pci/devices/0000:00:17.0/class').write_text('garbage')
    assert detect_storage_mode(tmp_path) is None


def test_snapshot_mode():
    assert storage_mode_from_snapshot({'storage_mode': 'vmd'}) == 'vmd'
    assert storage_mode_from_snapshot({'storage_mode': 'x'}) is None
    assert storage_mode_from_snapshot(json.loads((FIX / 'disks_linux_only.json').read_text())) is None


def test_error_message_both_langs():
    for lang in ('en', 'fr'):
        m = error_message(ErrorCode.RAID_MODE, lang)
        assert m['code'] == 'ME-RAID-MODE' and 'AHCI' in m['action'] and 'safeboot' in m['action']


def answers(target='gone'):
    return Answers(Language.EN, ProfileId.HOME, target, 'x', 1, InstallMode.LINUX_ONLY,
                   LinuxSizePreset.FULL_DISK, 'T', 'tech', 'pw', 'tech-pc')


def test_preflight_missing_target_maps_to_raid():
    disks = disks_from_snapshot(json.loads((FIX / 'disks_linux_only.json').read_text()))
    assert run_preflight(answers(), disks).error == ErrorCode.DISK_GONE
    assert run_preflight(answers(), disks, storage_mode=None).error == ErrorCode.DISK_GONE
    assert run_preflight(answers(), disks, storage_mode='vmd').error == ErrorCode.RAID_MODE
    assert run_preflight(answers('wwn-nvme0'), disks, storage_mode='vmd').ok


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_disk_page_banner(app):
    from memex_wizard.main_window import MainWindow
    w = MainWindow(demo=True)
    try:
        page = w.disk_page
        page._populate()
        assert page.raid_banner.isHidden() and page.list.count()
        w.storage_mode = 'vmd'
        page._populate()
        assert not page.raid_banner.isHidden()
        assert 'ME-RAID-MODE' in page.raid_banner.text() and 'AHCI' in page.raid_banner.text()
        assert page.validate()  # disks visible: warn but allow
        w.disks = []
        page._populate()
        assert not page.validate() and not page.raid_banner.isHidden()
    finally:
        w.close()


def test_demo_fixture_storage_mode_shows_banner():
    from PySide6.QtWidgets import QApplication
    from memex_wizard.main_window import MainWindow
    QApplication.instance() or QApplication([])
    win = MainWindow(demo=True, fixture_name="disks_vmd.json")
    assert win.storage_mode == "vmd"
    win.stack.setCurrentWidget(win.disk_page)
    win.disk_page._populate()
    assert not win.disk_page.raid_banner.isHidden()


def test_live_preflight_maps_missing_target_to_raid_mode(monkeypatch):
    from memex_engine import backend
    from memex_installer.errors import ErrorCode
    from memex_installer.models import Answers, InstallMode, Language, LinuxSizePreset, ProfileId
    monkeypatch.setattr(backend, "detect_storage_mode", lambda: "vmd")
    answers = Answers(language=Language.EN, profile=ProfileId.HOME, target_disk_id="gone",
                      target_disk_model="X", target_disk_size_bytes=1, mode=InstallMode.LINUX_ONLY,
                      linux_size=LinuxSizePreset.FULL_DISK, display_name="A", username="a",
                      password="pw", hostname="a-pc")
    result, _ = backend.checked_preflight(answers, [], inspect=lambda d: [])
    assert result.error == ErrorCode.RAID_MODE
