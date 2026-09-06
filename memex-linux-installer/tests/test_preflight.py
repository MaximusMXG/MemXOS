import json
from pathlib import Path

from memex_installer.disks import disks_from_snapshot
from memex_installer.errors import ErrorCode
from memex_installer.models import (
    Answers,
    InstallMode,
    Language,
    LinuxSizePreset,
    ProfileId,
)
from memex_installer.preflight import MIN_WINDOWS_BYTES, run_preflight

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return disks_from_snapshot(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def _answers(**kwargs) -> Answers:
    base = dict(
        language=Language.EN,
        profile=ProfileId.HOME,
        target_disk_id="wwn-nvme0",
        target_disk_model="disk",
        target_disk_size_bytes=1_000_000_000_000,
        mode=InstallMode.LINUX_ONLY,
        linux_size=LinuxSizePreset.FULL_DISK,
        display_name="Alex",
        username="alex",
        password="x",
        hostname="alex-pc",
    )
    base.update(kwargs)
    return Answers(**base)


def test_usb_target_rejected():
    disks = _load("disks_linux_only.json")
    result = run_preflight(
        _answers(target_disk_id="usb-installer", mode=InstallMode.LINUX_ONLY),
        disks,
    )
    assert result.error == ErrorCode.USB_TARGET
    assert not result.ok


def test_bitlocker_same_disk_rejected():
    disks = _load("disks_bitlocker.json")
    result = run_preflight(
        _answers(
            mode=InstallMode.DUAL_BOOT,
            linux_size=LinuxSizePreset.GB_100,
            target_disk_id="wwn-nvme0",
        ),
        disks,
    )
    assert result.error == ErrorCode.BITLOCKER


def test_two_disk_dual_boot_warns_and_ok():
    disks = _load("disks_dual_two.json")
    result = run_preflight(
        _answers(
            mode=InstallMode.DUAL_BOOT,
            target_disk_id="wwn-nvme-linux",
            linux_size=LinuxSizePreset.FULL_DISK,
        ),
        disks,
    )
    assert result.ok
    assert result.warning == ErrorCode.TWO_DISK
    assert result.plan is not None
    assert result.plan.wipes_target is True
    assert result.plan.two_disk_dual_boot is True


def test_dual_boot_no_windows_rejected():
    disks = _load("disks_linux_only.json")
    result = run_preflight(
        _answers(mode=InstallMode.DUAL_BOOT, linux_size=LinuxSizePreset.GB_100),
        disks,
    )
    assert result.error == ErrorCode.NO_WINDOWS


def test_same_disk_shrink_space_fail():
    disks = _load("disks_dual_same.json")
    # Force tiny disk by mutating
    for d in disks:
        if d.id == "wwn-nvme0":
            d.size_bytes = MIN_WINDOWS_BYTES + 10_000_000_000  # 64G + 10G
    result = run_preflight(
        _answers(
            mode=InstallMode.DUAL_BOOT,
            linux_size=LinuxSizePreset.HALF,  # ~37G linux, windows ~37G < 64G
            target_disk_id="wwn-nvme0",
            target_disk_size_bytes=MIN_WINDOWS_BYTES + 10_000_000_000,
        ),
        disks,
    )
    assert result.error == ErrorCode.SPACE


def test_linux_only_ok():
    disks = _load("disks_linux_only.json")
    result = run_preflight(_answers(mode=InstallMode.LINUX_ONLY), disks)
    assert result.ok
    assert result.plan is not None
    assert result.plan.wipes_target


def test_same_disk_dual_boot_ok():
    disks = _load("disks_dual_same.json")
    result = run_preflight(
        _answers(
            mode=InstallMode.DUAL_BOOT,
            linux_size=LinuxSizePreset.GB_100,
            target_disk_id="wwn-nvme0",
        ),
        disks,
    )
    assert result.ok
    assert result.plan is not None
    assert result.plan.shrinks_windows
    assert result.warning is None


def test_disk_gone():
    disks = _load("disks_linux_only.json")
    result = run_preflight(_answers(target_disk_id="missing"), disks)
    assert result.error == ErrorCode.DISK_GONE
