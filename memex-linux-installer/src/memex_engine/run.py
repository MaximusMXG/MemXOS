"""CLI: memex-engine /path/to/answers.yaml"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from memex_engine.autoinstall import write_autoinstall
from memex_engine.partition import execute_plan
from memex_engine.seed import seed_target
from memex_installer.answers_io import load_answers
from memex_installer.disks import discover_disks, disks_from_snapshot, find_disk
from memex_installer.errors import ErrorCode, error_message
from memex_installer.preflight import run_preflight


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Memory Express Linux installer engine")
    parser.add_argument("answers", type=Path, help="Path to answers.yaml")
    parser.add_argument("--fixture", type=Path, help="Use disk fixture JSON instead of lsblk")
    parser.add_argument("--autoinstall-out", type=Path, default=Path("/tmp/memex-autoinstall.yaml"))
    parser.add_argument("--seed-root", type=Path, help="Optional rootfs to seed (dry/dev)")
    args = parser.parse_args(argv)

    answers = load_answers(args.answers)
    if args.fixture:
        import json as _json

        disks = disks_from_snapshot(_json.loads(args.fixture.read_text(encoding="utf-8")))
    else:
        disks = discover_disks()

    result = run_preflight(answers, disks)
    if not result.ok or result.plan is None:
        code = result.error or ErrorCode.INSTALL_FAIL
        print(json.dumps(error_message(code, answers.language.value)), file=sys.stderr)
        return 2

    target = find_disk(disks, answers.target_disk_id)
    if target is None:
        print(json.dumps(error_message(ErrorCode.DISK_GONE, answers.language.value)), file=sys.stderr)
        return 2

    logs = execute_plan(result.plan, target)
    for line in logs:
        print(line)

    write_autoinstall(args.autoinstall_out, answers, result.plan)
    print(f"Wrote autoinstall to {args.autoinstall_out}")

    if args.seed_root:
        seed_target(args.seed_root, answers.profile, answers.language)
        print(f"Seeded {args.seed_root}")

    if result.warning:
        print(json.dumps(error_message(result.warning, answers.language.value)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
