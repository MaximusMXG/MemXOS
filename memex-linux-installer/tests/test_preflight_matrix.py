"""Parametrized preflight matrix covering spec §12 logic cases."""

import json
from pathlib import Path

import pytest

from memex_installer.disks import disks_from_snapshot
from memex_installer.errors import ErrorCode
from memex_installer.models import (
    Answers,
    InstallMode,
    Language,
    LinuxSizePreset,
    ProfileId,
)
from memex_installer.preflight import run_preflight

FIXTURES = Path(__file__).parent / "fixtures"


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


@pytest.mark.parametrize(
    "fixture,kwargs,expect_ok,expect_error,expect_warning",
    [
        ("disks_linux_only.json", {"mode": InstallMode.LINUX_ONLY}, True, None, None),
        (
            "disks_dual_same.json",
            {"mode": InstallMode.DUAL_BOOT, "linux_size": LinuxSizePreset.GB_100},
            True,
            None,
            None,
        ),
        (
            "disks_dual_two.json",
            {
                "mode": InstallMode.DUAL_BOOT,
                "target_disk_id": "wwn-nvme-linux",
                "linux_size": LinuxSizePreset.FULL_DISK,
            },
            True,
            None,
            ErrorCode.TWO_DISK,
        ),
        (
            "disks_bitlocker.json",
            {"mode": InstallMode.DUAL_BOOT, "linux_size": LinuxSizePreset.GB_100},
            False,
            ErrorCode.BITLOCKER,
            None,
        ),
        (
            "disks_linux_only.json",
            {"mode": InstallMode.DUAL_BOOT, "linux_size": LinuxSizePreset.GB_100},
            False,
            ErrorCode.NO_WINDOWS,
            None,
        ),
        (
            "disks_linux_only.json",
            {"mode": InstallMode.LINUX_ONLY, "target_disk_id": "usb-installer"},
            False,
            ErrorCode.USB_TARGET,
            None,
        ),
    ],
)
def test_preflight_matrix(fixture, kwargs, expect_ok, expect_error, expect_warning):
    disks = disks_from_snapshot(json.loads((FIXTURES / fixture).read_text(encoding="utf-8")))
    result = run_preflight(_answers(**kwargs), disks)
    assert result.ok is expect_ok
    assert result.error == expect_error
    assert result.warning == expect_warning
