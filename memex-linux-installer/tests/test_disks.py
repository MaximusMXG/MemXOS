import json
from pathlib import Path

from memex_installer.disks import disks_from_snapshot

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_usb_installer_flagged():
    disks = disks_from_snapshot(load_fixture("disks_linux_only.json"))
    assert any(d.is_usb for d in disks)
    assert any(not d.is_usb for d in disks)


def test_windows_badge():
    disks = disks_from_snapshot(load_fixture("disks_dual_same.json"))
    win = [d for d in disks if d.has_windows]
    assert len(win) == 1
    assert win[0].bitlocker_on is False


def test_bitlocker_flag():
    disks = disks_from_snapshot(load_fixture("disks_bitlocker.json"))
    win = next(d for d in disks if d.has_windows)
    assert win.bitlocker_on is True


def test_two_disk_fixture():
    disks = disks_from_snapshot(load_fixture("disks_dual_two.json"))
    assert sum(1 for d in disks if d.has_windows) == 1
    assert sum(1 for d in disks if not d.is_usb) == 2
