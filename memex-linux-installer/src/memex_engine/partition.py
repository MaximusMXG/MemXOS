"""Preview partition intent. Real disk mutation is not implemented or enabled."""

from __future__ import annotations

import os
from dataclasses import dataclass

from memex_installer.models import DiskInfo, PartitionPlan


@dataclass
class PlannedOp:
    description: str
    command: list[str]


def plan_operations(plan: PartitionPlan, target: DiskInfo) -> list[PlannedOp]:
    ops: list[PlannedOp] = []
    if plan.wipes_target:
        ops.append(
            PlannedOp(
                description=f"Wipe and GPT-partition {target.device_path}",
                command=["sgdisk", "--zap-all", target.device_path],
            )
        )
        ops.append(
            PlannedOp(
                description="Create EFI + root partitions",
                command=["sgdisk", "-n", "1:0:+512M", "-t", "1:ef00", "-n", "2:0:0", "-t", "2:8300", target.device_path],
            )
        )
    elif plan.shrinks_windows:
        ops.append(
            PlannedOp(
                description=f"Shrink Windows NTFS on {target.device_path} for {plan.linux_size_bytes} bytes Linux",
                command=[],
            )
        )
        ops.append(
            PlannedOp(
                description="Create Linux partitions in freed space",
                command=[],
            )
        )
    return ops


def execute_plan(plan: PartitionPlan, target: DiskInfo) -> list[str]:
    """Return previews only; reject the obsolete destructive environment switch."""
    if os.environ.get("MEMEX_DRY_RUN") == "0":
        raise RuntimeError("Real installation is unavailable in this development build.")
    logs: list[str] = []
    for op in plan_operations(plan, target):
        line = f"[preview] {op.description}"
        logs.append(line)
    return logs
