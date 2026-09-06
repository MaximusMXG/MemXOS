"""Partition helpers. Dry-run by default unless MEMEX_DRY_RUN=0."""

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
                command=["ntfsresize", "--info", target.device_path],
            )
        )
        ops.append(
            PlannedOp(
                description="Create Linux partitions in freed space",
                command=["sgdisk", "-n", "0:0:0", "-t", "0:8300", target.device_path],
            )
        )
    return ops


def execute_plan(plan: PartitionPlan, target: DiskInfo) -> list[str]:
    """Return log lines. Only runs commands when MEMEX_DRY_RUN=0."""
    dry_run = os.environ.get("MEMEX_DRY_RUN", "1") != "0"
    logs: list[str] = []
    for op in plan_operations(plan, target):
        line = f"{'[dry-run] ' if dry_run else ''}{op.description}: {' '.join(op.command)}"
        logs.append(line)
        if not dry_run:
            import subprocess

            subprocess.run(op.command, check=True)
    return logs
