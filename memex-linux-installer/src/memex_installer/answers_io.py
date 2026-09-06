"""Read/write answers.yaml for the live installer session.

The password field is only for generating autoinstall during install.
seed.py must never copy the password into the installed OS.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from memex_installer.secure_io import atomic_write, password_hash
from memex_installer.models import (
    Answers,
    InstallMode,
    Language,
    LinuxSizePreset,
    ProfileId,
)


def save_answers(path: Path, answers: Answers) -> None:
    data = {
        "language": answers.language.value,
        "profile": answers.profile.value,
        "target_disk_id": answers.target_disk_id,
        "target_disk_model": answers.target_disk_model,
        "target_disk_size_bytes": answers.target_disk_size_bytes,
        "mode": answers.mode.value,
        "linux_size": answers.linux_size.value,
        "display_name": answers.display_name,
        "username": answers.username,
        "password": password_hash(answers.password),
        "hostname": answers.hostname,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, yaml.safe_dump(data, sort_keys=False))


def load_answers(path: Path) -> Answers:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Answers(
        language=Language(data["language"]),
        profile=ProfileId(data["profile"]),
        target_disk_id=data["target_disk_id"],
        target_disk_model=data["target_disk_model"],
        target_disk_size_bytes=int(data["target_disk_size_bytes"]),
        mode=InstallMode(data["mode"]),
        linux_size=LinuxSizePreset(data["linux_size"]),
        display_name=data["display_name"],
        username=data["username"],
        password=data["password"],
        hostname=data["hostname"],
    )
