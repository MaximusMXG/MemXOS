"""Preflight dual-boot / wipe safety rules (spec §6)."""

from __future__ import annotations

from dataclasses import dataclass

from memex_installer.disks import find_disk
from memex_installer.errors import ErrorCode
from memex_installer.sizing import MIN_WINDOWS, linux_size_for, size_fits
from memex_installer.models import (
    Answers,
    DiskInfo,
    InstallMode,
    LinuxSizePreset,
    PartitionPlan,
)

MIN_WINDOWS_BYTES = MIN_WINDOWS


@dataclass
class PreflightResult:
    ok: bool
    error: ErrorCode | None = None
    warning: ErrorCode | None = None
    plan: PartitionPlan | None = None
    estimated: bool = False  # same-disk size derived from whole-disk size, not the NTFS partition


def run_preflight(answers: Answers, disks: list[DiskInfo], *, win_size: int | None = None,
                  win_min: int | None = None) -> PreflightResult:
    """win_size/win_min: exact Windows NTFS partition size and resize minimum (read-only inspection).

    Without them, same-disk sizing is estimated from the whole disk and flagged `estimated`."""
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

        estimated = win_size is None
        base = target.size_bytes if estimated else win_size
        preset = (LinuxSizePreset.ALL_LEFTOVER if answers.linux_size == LinuxSizePreset.FULL_DISK
                  else answers.linux_size)
        linux_bytes = linux_size_for(preset, base, win_min)
        if not size_fits(linux_bytes, base, win_min):
            return PreflightResult(ok=False, error=ErrorCode.SPACE, estimated=estimated)

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
            estimated=estimated,
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
