"""CLI for development previews; this build cannot install an OS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from memex_engine.preview import build_preview
from memex_engine.backend import inspect_partitions, install
from memex_engine.seed import seed_target
from memex_installer.answers_io import load_answers
from memex_installer.disks import discover_disks, disks_from_snapshot
from memex_installer.errors import ErrorCode, MemexError, error_message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Memory Express installation preview (no disk changes)")
    parser.add_argument("answers", type=Path)
    parser.add_argument("--fixture", type=Path, help="Use fixture disks instead of live discovery")
    parser.add_argument("--preview-out", type=Path, help="Save a password-free JSON preview")
    parser.add_argument("--seed-root", type=Path, help="Seed a new, empty development directory")
    parser.add_argument("--install", action="store_true", help="Install from the MemXOS live ISO")
    parser.add_argument("--confirm-disk", help="Exact confirmed stable disk identifier")
    args = parser.parse_args(argv)
    lang = "en"
    try:
        answers = load_answers(args.answers)
        lang = answers.language.value
        if args.install:
            if args.fixture or args.seed_root or args.preview_out:
                raise ValueError("Installation cannot use fixtures or development outputs.")
            install(answers, args.confirm_disk)
            print(json.dumps({"status": "os_installed", "installed": True, "setup_complete": False}))
            return 0
        disks = (disks_from_snapshot(json.loads(args.fixture.read_text(encoding="utf-8")))
                 if args.fixture else discover_disks())
        report = build_preview(answers, disks, None if args.fixture else inspect_partitions)
        if report["status"] == "blocked":
            print(json.dumps(report), file=sys.stderr)
            return 2
        if args.seed_root:
            root = args.seed_root.resolve()
            # Development seeding must never replace an existing installed system.
            if root.exists() and (not root.is_dir() or any(root.iterdir())):
                raise ValueError("Development seed destination must be a new or empty directory.")
            seed_target(root, answers.profile, answers.language)
            report["seed_root"] = str(root)
        output = json.dumps(report, indent=2)
        if args.preview_out:
            args.preview_out.parent.mkdir(parents=True, exist_ok=True)
            args.preview_out.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0
    except Exception as exc:  # Convert discovery, YAML and I/O failures to a safe CLI result.
        # Do not expose raw parser exceptions: they can contain customer credentials.
        # Only typed MemexError codes are surfaced; everything else stays generic.
        error = error_message(exc.code if isinstance(exc, MemexError) else ErrorCode.INSTALL_FAIL, lang)
        error["reason"] = type(exc).__name__
        print(json.dumps({"status": "blocked", "installed": False, "disk_changes": False, "error": error}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
