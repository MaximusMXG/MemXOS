"""Preflight dual-boot / wipe safety rules (spec §6)."""

from __future__ import annotations

from dataclasses import dataclass

from memex_installer.disks import find_disk
from memex_installer.errors import ErrorCode
from memex_installer.models import (
    Answers,
    DiskInfo,
    InstallMode,
    LinuxSizePreset,
    PartitionPlan,
)

MIN_WINDOWS_BYTES = 64 * 1024**3
GB_100 = 100 * 1024**3


@dataclass
class PreflightResult:
    ok: bool
    error: ErrorCode | None = None
    warning: ErrorCode | None = None
    plan: PartitionPlan | None = None


def _linux_bytes_for_same_disk(disk: DiskInfo, preset: LinuxSizePreset) -> int:
    if preset == LinuxSizePreset.GB_100:
        return GB_100
    if preset == LinuxSizePreset.HALF:
        return disk.size_bytes // 2
    if preset == LinuxSizePreset.ALL_LEFTOVER:
        # Leave minimum Windows floor; rest to Linux.
        return max(0, disk.size_bytes - MIN_WINDOWS_BYTES)
    # FULL_DISK on same-disk dual-boot is invalid; treat as all leftover.
    return max(0, disk.size_bytes - MIN_WINDOWS_BYTES)


def run_preflight(answers: Answers, disks: list[DiskInfo]) -> PreflightResult:
    target = find_disk(disks, answers.target_disk_id)
    if target is None:
        return PreflightResult(ok=False, error=ErrorCode.DISK_GONE)

    if target.is_usb:
        return PreflightResult(ok=False, error=ErrorCode.USB_TARGET)

    windows_disks = [d for d in disks if d.has_windows and not d.is_usb]

    if answers.mode == InstallMode.LINUX_ONLY:
        return PreflightResult(
            ok=True,
            plan=PartitionPlan(
                target_disk_id=target.id,
                wipes_target=True,
                shrinks_windows=False,
                two_disk_dual_boot=False,
                linux_size_bytes=target.size_bytes,
            ),
        )

    # Dual-boot
    if not windows_disks:
        return PreflightResult(ok=False, error=ErrorCode.NO_WINDOWS)

    on_same = target.has_windows
    if on_same:
        if target.bitlocker_on:
            return PreflightResult(ok=False, error=ErrorCode.BITLOCKER)

        linux_bytes = _linux_bytes_for_same_disk(target, answers.linux_size)
        windows_remaining = target.size_bytes - linux_bytes
        if linux_bytes <= 0 or windows_remaining < MIN_WINDOWS_BYTES:
            return PreflightResult(ok=False, error=ErrorCode.SPACE)

        return PreflightResult(
            ok=True,
            plan=PartitionPlan(
                target_disk_id=target.id,
                wipes_target=False,
                shrinks_windows=True,
                two_disk_dual_boot=False,
                linux_size_bytes=linux_bytes,
                windows_disk_id=target.id,
            ),
        )

    # Windows on a different disk — preferred two-drive layout
    other_windows = next((d for d in windows_disks if d.id != target.id), None)
    if other_windows is None:
        return PreflightResult(ok=False, error=ErrorCode.NO_WINDOWS)

    return PreflightResult(
        ok=True,
        warning=ErrorCode.TWO_DISK,
        plan=PartitionPlan(
            target_disk_id=target.id,
            wipes_target=True,
            shrinks_windows=False,
            two_disk_dual_boot=True,
            linux_size_bytes=target.size_bytes,
            windows_disk_id=other_windows.id,
        ),
    )
