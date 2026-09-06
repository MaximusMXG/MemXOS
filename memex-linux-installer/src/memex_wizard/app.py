"""memex-wizard entrypoint."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from memex_wizard.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Memory Express Linux installer wizard")
    parser.add_argument("--demo", action="store_true", help="Use fixture disks; never wipe hardware")
    parser.add_argument("--fixture", default="disks_dual_two.json")
    args, qt_args = parser.parse_known_args(argv)

    app = QApplication([sys.argv[0], *qt_args] if argv is None else [sys.argv[0], *qt_args])
    window = MainWindow(demo=args.demo, fixture_name=args.fixture)
    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
