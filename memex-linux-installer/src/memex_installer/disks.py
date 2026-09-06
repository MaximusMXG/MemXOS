"""Disk discovery with injectable command runner for tests."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

from memex_installer.models import DiskInfo

Runner = Callable[[list[str]], str]


def _default_runner(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


def disks_from_snapshot(data: dict[str, Any]) -> list[DiskInfo]:
    disks: list[DiskInfo] = []
    for item in data.get("disks", []):
        disks.append(
            DiskInfo(
                id=item["id"],
                model=item.get("model") or "Unknown",
                size_bytes=int(item["size_bytes"]),
                device_path=item["device_path"],
                is_usb=bool(item.get("is_usb", False)),
                has_windows=bool(item.get("has_windows", False)),
                bitlocker_on=bool(item.get("bitlocker_on", False)),
            )
        )
    return disks


def _parse_size(size: str | int | None) -> int:
    if size is None:
        return 0
    if isinstance(size, int):
        return size
    size = size.strip().upper()
    units = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    if size[-1] in units:
        return int(float(size[:-1]) * units[size[-1]])
    return int(size)


def discover_disks(runner: Runner | None = None) -> list[DiskInfo]:
    """Discover block disks via lsblk JSON.

    Windows / BitLocker live heuristics are best-effort. Tests use
    disks_from_snapshot with explicit flags.
    """
    run = runner or _default_runner
    raw = run(
        [
            "lsblk",
            "-J",
            "-b",
            "-o",
            "NAME,SIZE,MODEL,TRAN,TYPE,PKNAME,FSTYPE,MOUNTPOINT,SERIAL,WWN",
        ]
    )
    payload = json.loads(raw)
    disks: list[DiskInfo] = []

    for device in payload.get("blockdevices", []):
        if device.get("type") != "disk":
            continue
        children = device.get("children") or []
        has_windows = False
        bitlocker_on = False
        for child in children:
            fstype = (child.get("fstype") or "").lower()
            if fstype == "ntfs":
                has_windows = True
            if "bitlocker" in fstype or fstype == "fve-fs":
                bitlocker_on = True
                has_windows = True

        serial = device.get("serial") or device.get("wwn") or device.get("name")
        model = (device.get("model") or "Unknown").strip()
        tran = (device.get("tran") or "").lower()
        name = device.get("name")
        disks.append(
            DiskInfo(
                id=str(serial),
                model=model,
                size_bytes=_parse_size(device.get("size")),
                device_path=f"/dev/{name}",
                is_usb=tran == "usb",
                has_windows=has_windows,
                bitlocker_on=bitlocker_on,
            )
        )
    return disks


def find_disk(disks: list[DiskInfo], disk_id: str) -> DiskInfo | None:
    for disk in disks:
        if disk.id == disk_id or disk.device_path == disk_id:
            return disk
    return None
