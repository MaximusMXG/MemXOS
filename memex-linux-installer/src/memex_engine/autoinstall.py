from __future__ import annotations

from pathlib import Path

import yaml

from memex_installer.models import Answers, Language, PartitionPlan


def _locale_keyboard(answers: Answers) -> tuple[str, str]:
    if answers.language == Language.FR:
        return "fr_CA.UTF-8", "ca"
    return "en_CA.UTF-8", "us"


def build_autoinstall(answers: Answers, plan: PartitionPlan) -> dict:
    """Build Ubuntu autoinstall dict from Answers + PartitionPlan."""
    locale, keyboard = _locale_keyboard(answers)
    if plan.wipes_target:
        storage: dict = {
            "layout": {
                "name": "direct",
                "match": {"path": plan.target_disk_id},
            }
        }
    else:
        storage = {
            "layout": {
                "name": "direct",
                "match": {"path": plan.target_disk_id},
                "sizing_policy": "scaled",
            },
            "memex_shrink_windows_bytes": plan.linux_size_bytes,
        }

    return {
        "autoinstall": {
            "version": 1,
            "locale": locale,
            "keyboard": {"layout": keyboard},
            "identity": {
                "hostname": answers.hostname,
                "realname": answers.display_name,
                "username": answers.username,
                "password": answers.password,
            },
            "storage": storage,
            "packages": ["timeshift"],
            "late-commands": [
                "curtin in-target -- mkdir -p /etc/memex",
                f"curtin in-target -- bash -c \"echo {answers.profile.value} > /etc/memex/profile\"",
                f"curtin in-target -- bash -c \"echo {answers.language.value} > /etc/memex/language\"",
            ],
            "shutdown": "reboot",
        }
    }


def write_autoinstall(path: Path, answers: Answers, plan: PartitionPlan) -> None:
    data = build_autoinstall(answers, plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
