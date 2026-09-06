"""Five-screen Memory Express installer wizard."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from memex_installer.answers_io import save_answers
from memex_installer.disks import disks_from_snapshot, discover_disks
from memex_installer.errors import error_message
from memex_installer.i18n_ui import t
from memex_installer.models import (
    Answers,
    DiskInfo,
    InstallMode,
    Language,
    LinuxSizePreset,
    ProfileId,
)
from memex_installer.preflight import run_preflight
from memex_installer.version import PRODUCT_VERSION
from memex_wizard.pages.account import AccountPage
from memex_wizard.pages.confirm import ConfirmPage
from memex_wizard.pages.disk import DiskPage
from memex_wizard.pages.language import LanguagePage
from memex_wizard.pages.pc_type import PcTypePage

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


class MainWindow(QMainWindow):
    def __init__(self, demo: bool = False, fixture_name: str = "disks_dual_two.json") -> None:
        super().__init__()
        self.demo = demo
        self.lang = "en"
        self.profile = ProfileId.HOME
        self.disks: list[DiskInfo] = []
        self.selected_disk_id = ""
        self.mode = InstallMode.LINUX_ONLY
        self.linux_size = LinuxSizePreset.FULL_DISK
        self.display_name = ""
        self.username = ""
        self.password = ""

        self.setWindowTitle(PRODUCT_VERSION)
        central = QWidget()
        self.setCentralWidget(central)
        self.layout = QVBoxLayout(central)

        self.version_label = QLabel(PRODUCT_VERSION)
        self.layout.addWidget(self.version_label)

        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        self.language_page = LanguagePage(self)
        self.pc_type_page = PcTypePage(self)
        self.disk_page = DiskPage(self)
        self.account_page = AccountPage(self)
        self.confirm_page = ConfirmPage(self)
        for page in (
            self.language_page,
            self.pc_type_page,
            self.disk_page,
            self.account_page,
            self.confirm_page,
        ):
            self.stack.addWidget(page)

        nav = QHBoxLayout()
        self.back_btn = QPushButton()
        self.next_btn = QPushButton()
        self.back_btn.clicked.connect(self.go_back)
        self.next_btn.clicked.connect(self.go_next)
        nav.addWidget(self.back_btn)
        nav.addStretch()
        nav.addWidget(self.next_btn)
        self.layout.addLayout(nav)

        self._load_disks(fixture_name)
        self.retranslate()
        self.stack.setCurrentIndex(0)
        self._update_nav()

    def _load_disks(self, fixture_name: str) -> None:
        if self.demo:
            path = FIXTURES / fixture_name
            self.disks = disks_from_snapshot(json.loads(path.read_text(encoding="utf-8")))
        else:
            try:
                self.disks = discover_disks()
            except Exception:  # noqa: BLE001
                path = FIXTURES / fixture_name
                self.disks = disks_from_snapshot(json.loads(path.read_text(encoding="utf-8")))

    def retranslate(self) -> None:
        self.setWindowTitle(t(self.lang, "app_title"))
        self.back_btn.setText(t(self.lang, "back"))
        self._update_nav()
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "retranslate"):
                page.retranslate()

    def _update_nav(self) -> None:
        idx = self.stack.currentIndex()
        self.back_btn.setEnabled(idx > 0)
        if idx == self.stack.count() - 1:
            self.next_btn.setText(t(self.lang, "install"))
        else:
            self.next_btn.setText(t(self.lang, "next"))

    def go_back(self) -> None:
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav()

    def go_next(self) -> None:
        idx = self.stack.currentIndex()
        page = self.stack.widget(idx)
        if hasattr(page, "validate") and not page.validate():
            return
        if idx == self.stack.count() - 1:
            self._install()
            return
        self.stack.setCurrentIndex(idx + 1)
        self._update_nav()

    def build_answers(self) -> Answers:
        disk = next(d for d in self.disks if d.id == self.selected_disk_id)
        return Answers(
            language=Language.FR if self.lang.startswith("fr") else Language.EN,
            profile=self.profile,
            target_disk_id=disk.id,
            target_disk_model=disk.model,
            target_disk_size_bytes=disk.size_bytes,
            mode=self.mode,
            linux_size=self.linux_size,
            display_name=self.display_name,
            username=self.username,
            password=self.password,
            hostname=Answers.hostname_for(self.username),
        )

    def _install(self) -> None:
        answers = self.build_answers()
        result = run_preflight(answers, self.disks)
        if not result.ok and result.error:
            msg = error_message(result.error, self.lang)
            QMessageBox.critical(self, msg["title"], f"{msg['body']}\n\n{msg['action']}\n({msg['code']})")
            return
        if result.warning:
            warn = error_message(result.warning, self.lang)
            choice = QMessageBox.warning(
                self,
                warn["title"],
                f"{warn['body']}\n\n{warn['action']}\n({warn['code']})",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if choice != QMessageBox.StandardButton.Ok:
                return

        answers_path = Path(os.environ.get("MEMEX_ANSWERS_PATH", "/tmp/memex-answers.yaml"))
        save_answers(answers_path, answers)

        if self.demo:
            QMessageBox.information(
                self,
                t(self.lang, "reboot_title"),
                t(self.lang, "reboot_body").format(username=answers.username)
                + f"\n\n[demo] Saved {answers_path}",
            )
            return

        try:
            proc = subprocess.run(
                [sys.executable, "-m", "memex_engine.run", str(answers_path)],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            QMessageBox.critical(self, "Engine", str(exc))
            return

        if proc.returncode != 0:
            QMessageBox.critical(self, "Engine", proc.stderr or proc.stdout or "failed")
            return

        QMessageBox.information(
            self,
            t(self.lang, "reboot_title"),
            t(self.lang, "reboot_body").format(username=answers.username),
        )
