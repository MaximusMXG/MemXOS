"""Password-free installation previews shared by the CLI and wizard."""

from dataclasses import asdict

from memex_engine.partition import execute_plan
from memex_installer.disks import find_disk
from memex_engine.backend import checked_preflight
from memex_installer.errors import ErrorCode, MemexError, error_message
from memex_installer.models import Answers, DiskInfo


def build_preview(answers: Answers, disks: list[DiskInfo], inspect=None) -> dict:
    """`inspect` (live only, read-only) supplies exact NTFS sizes; without it same-disk sizes are estimates."""
    report = {"status": "blocked", "installed": False, "disk_changes": False}
    try:
        result, _ = checked_preflight(answers, disks, inspect)
    except MemexError as exc:
        report["error"] = error_message(exc.code, answers.language.value)
        return report
    except Exception:  # noqa: BLE001 - inspection failures must not leak raw text
        report["error"] = error_message(ErrorCode.INSTALL_FAIL, answers.language.value)
        return report
    if not result.ok or result.plan is None:
        report["error"] = error_message(result.error or ErrorCode.INSTALL_FAIL, answers.language.value)
        return report
    target = find_disk(disks, answers.target_disk_id)
    if target.model != answers.target_disk_model or target.size_bytes != answers.target_disk_size_bytes:
        report["error"] = error_message(ErrorCode.DISK_GONE, answers.language.value)
        return report
    report.update({
        "status": "preview_ready",
        "target": asdict(target),
        "plan": asdict(result.plan),
        "profile": answers.profile.value,
        "operations": execute_plan(result.plan, target),
        "warning": error_message(result.warning, answers.language.value) if result.warning else None,
        "size_estimated": result.estimated,
        "limitations": ["Preview only: no operating system has been installed."] + (
            ["Same-disk resizing requires partition and filesystem validation; the size is an estimate."]
            if result.plan.shrinks_windows and result.estimated else []
        ),
    })
    return report
