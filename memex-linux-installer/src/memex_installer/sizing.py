"""Single source of truth for same-disk Linux sizing (used by preflight and the storage engine)."""

from __future__ import annotations

from memex_installer.models import LinuxSizePreset

MIB = 1024**2
GIB = 1024**3
MIN_LINUX = 40 * GIB
MIN_WINDOWS = 64 * GIB


def windows_floor(win_min: int | None = None) -> int:
    """Smallest size Windows may keep: 64 GiB, or the NTFS minimum plus 2 GiB if larger."""
    if win_min is None:
        return MIN_WINDOWS
    return max(MIN_WINDOWS, ((win_min + 2 * GIB + MIB - 1) // MIB) * MIB)


def linux_size_for(preset: LinuxSizePreset, win_size: int, win_min: int | None = None) -> int | None:
    """Requested Linux bytes carved from a Windows volume of win_size; None if the preset is invalid here."""
    if preset == LinuxSizePreset.GB_100:
        return 100 * GIB
    if preset == LinuxSizePreset.HALF:
        return (win_size // (2 * MIB)) * MIB
    if preset == LinuxSizePreset.ALL_LEFTOVER:
        return max(0, ((win_size - windows_floor(win_min)) // MIB) * MIB)
    return None


def size_fits(linux: int | None, win_size: int, win_min: int | None = None) -> bool:
    return (linux is not None and linux >= MIN_LINUX
            and win_size - linux >= windows_floor(win_min))
