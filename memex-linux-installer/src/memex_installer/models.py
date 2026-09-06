from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


class Language(Enum):
    EN = "en"
    FR = "fr"


class ProfileId(Enum):
    HOME = "home"
    WORKSTATION = "workstation"
    GAMING = "gaming"


class InstallMode(Enum):
    LINUX_ONLY = "linux_only"
    DUAL_BOOT = "dual_boot"


class LinuxSizePreset(Enum):
    HALF = "half"
    GB_100 = "100gb"
    ALL_LEFTOVER = "all_leftover"
    FULL_DISK = "full_disk"


@dataclass
class Answers:
    language: Language
    profile: ProfileId
    target_disk_id: str
    target_disk_model: str
    target_disk_size_bytes: int
    mode: InstallMode
    linux_size: LinuxSizePreset
    display_name: str
    username: str
    password: str
    hostname: str

    @staticmethod
    def hostname_for(username: str) -> str:
        clean = re.sub(r"[^a-z0-9_-]", "", username.lower())
        return f"{clean or 'user'}-pc"

    @staticmethod
    def username_from_display(display_name: str) -> str:
        first = display_name.strip().split()[0] if display_name.strip() else "user"
        return re.sub(r"[^a-z0-9]", "", first.lower()) or "user"


@dataclass
class DiskInfo:
    id: str
    model: str
    size_bytes: int
    device_path: str
    is_usb: bool = False
    has_windows: bool = False
    bitlocker_on: bool = False


@dataclass
class PartitionPlan:
    target_disk_id: str
    wipes_target: bool
    shrinks_windows: bool
    two_disk_dual_boot: bool
    linux_size_bytes: int | None = None
    windows_disk_id: str | None = None


@dataclass
class PackageLists:
    apt: list[str]
    flatpak: list[str]
    special: list[str]
