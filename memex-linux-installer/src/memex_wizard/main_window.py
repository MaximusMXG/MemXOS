"""Five-screen Memory Express installer wizard."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import time

from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from memex_engine.preview import build_preview
from memex_engine.backend import inspect_partitions, live_available
from memex_installer.answers_io import save_answers
from memex_installer.disks import detect_storage_mode, disks_from_snapshot, discover_disks, storage_mode_from_snapshot
from memex_installer.errors import ErrorCode, error_message
from memex_installer.i18n_ui import t
from memex_installer.models import (
    Answers,
    DiskInfo,
    InstallMode,
    Language,
    LinuxSizePreset,
    ProfileId,
)
from memex_installer.store import DEFAULT_TIMEZONE, Store, load_store
from memex_installer.version import PRODUCT_VERSION
from memex_wizard.pages.account import AccountPage
from memex_wizard.pages.confirm import ConfirmPage
from memex_wizard.pages.disk import DiskPage
from memex_wizard.pages.language import LanguagePage
from memex_wizard.pages.pc_type import PcTypePage
from memex_wizard import progress

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


class MainWindow(QMainWindow):
    def __init__(self, demo: bool = False, fixture_name: str = "disks_dual_two.json",
                 store_path: Path | None = None, store: Store | None = None) -> None:
        super().__init__()
        self.demo = demo
        self.install_enabled = not demo and os.geteuid() == 0 and live_available()
        self.engine_process = None
        self.engine_log = progress.ENGINE_LOG
        self.engine_started = 0.0
        self.engine_log_offset = 0
        self.install_session = None
        self.lang = "en"
        self.store_error = False
        try:
            if store is not None:
                self.store = store
            elif store_path is None and demo:
                self.store = Store()
            else:
                self.store = load_store(store_path) if store_path else load_store()
        except ValueError:
            self.store, self.store_error = Store(), True
        self.profile = ProfileId.HOME
        self.disks: list[DiskInfo] = []
        self.storage_mode: str | None = None
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
        self.store_label = QLabel()
        self.store_label.setWordWrap(True)
        self.layout.addWidget(self.store_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        self.layout.addWidget(self.progress_bar)
        self.stuck_label = QLabel()
        self.stuck_label.setWordWrap(True)
        self.stuck_label.setStyleSheet("color: #b00020; font-weight: bold;")
        self.stuck_label.hide()
        self.layout.addWidget(self.stuck_label)
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(2000)
        self.progress_timer.timeout.connect(self._update_progress)

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
        self.reboot_btn = QPushButton(t(self.lang, "restart_pc"))
        self.reboot_btn.clicked.connect(lambda: QProcess.startDetached("systemctl", ["reboot"]))
        self.reboot_btn.hide()
        self.layout.addWidget(self.reboot_btn)

        self._load_disks(fixture_name)
        self.retranslate()
        self.stack.setCurrentIndex(0)
        self._update_nav()

    def _load_disks(self, fixture_name: str) -> None:
        if self.demo:
            data = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
            self.disks = disks_from_snapshot(data)
            self.storage_mode = storage_mode_from_snapshot(data)
        else:
            try:
                self.disks = discover_disks()
            except Exception:  # noqa: BLE001
                self.disks = []
                msg = error_message(ErrorCode.RAID_MODE if detect_storage_mode() else ErrorCode.DISK_GONE, self.lang)
                QMessageBox.critical(self, msg["title"], msg["body"] + "\n" + msg["action"])

    def retranslate(self) -> None:
        self.setWindowTitle(t(self.lang, "app_title"))
        self.back_btn.setText(t(self.lang, "back"))
        self.reboot_btn.setText(t(self.lang, "restart_pc"))
        self._update_nav()
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "retranslate"):
                page.retranslate()

    def store_text(self) -> str:
        if self.store_error:
            return t(self.lang, "store_invalid")
        name = self.store.name or t(self.lang, "store_unset")
        tz = self.store.timezone
        if not self.store.name and tz == DEFAULT_TIMEZONE:
            tz = t(self.lang, "store_tz_default").format(tz=tz)
        return t(self.lang, "store_line").format(name=name, tz=tz)

    def _update_nav(self) -> None:
        idx = self.stack.currentIndex()
        self.store_label.setText(self.store_text())
        self.store_label.setStyleSheet("color: #b00020; font-weight: bold;" if self.store_error else "")
        self.store_label.setVisible(idx in (0, self.stack.count() - 1))
        self.back_btn.setEnabled(idx > 0)
        if idx == self.stack.count() - 1:
            self.next_btn.setText(t(self.lang, "install" if self.install_enabled else "preview"))
            self.confirm_page._refresh()
            running = self.engine_process is not None and self.engine_process.state() != QProcess.ProcessState.NotRunning
            self.next_btn.setEnabled(self.confirm_page.can_install() and not running)
        else:
            self.next_btn.setText(t(self.lang, "next"))
            self.next_btn.setEnabled(True)
        if self.store_error:
            self.next_btn.setEnabled(False)

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
        if self.store_error or not self.confirm_page.can_install():
            return
        try:
            answers = self.build_answers()
            # Keep the confirmed identity, then rediscover before building a live preview.
            disks = self.disks if self.demo else discover_disks()
            report = build_preview(answers, disks, inspect_partitions if self.install_enabled else None)
        except Exception:
            msg = error_message(ErrorCode.INSTALL_FAIL, self.lang)
            QMessageBox.critical(self, msg["title"], msg["body"] + "\n" + msg["action"])
            return
        if report["status"] == "blocked":
            msg = report["error"]
            QMessageBox.critical(self, msg["title"], f"{msg['body']}\n\n{msg['action']}\n({msg['code']})")
            return
        if self.install_enabled:
            confirm = QMessageBox.warning(self, t(self.lang, "confirm_title"),
                t(self.lang, "destructive_confirm").format(model=answers.target_disk_model),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if confirm != QMessageBox.StandardButton.Ok:
                return
            self._start_engine(answers)
            return
        body = t(self.lang, "preview_body")
        if report["warning"]:
            body += "\n\n" + report["warning"]["body"]
        if report["plan"]["shrinks_windows"]:
            body += "\n\n" + t(self.lang, "preview_shrink")
        QMessageBox.information(self, t(self.lang, "preview_title"), body)

    def _start_engine(self, answers):
        try:
            self.install_session = tempfile.TemporaryDirectory(prefix="memex-", dir="/run")
            path = Path(self.install_session.name) / "answers.yaml"
            save_answers(path, answers)
            self.engine_process = QProcess(self)
            self.engine_process.finished.connect(self._engine_finished)
            self.engine_process.errorOccurred.connect(self._engine_error)
            self.next_btn.setEnabled(False)
            self.back_btn.setEnabled(False)
            self.stack.setEnabled(False)
            self.version_label.setText(t(self.lang, "install_running"))
            self.engine_started = time.time()
            self.engine_log_offset = progress.log_size(self.engine_log)
            self.progress_bar.show()
            self.progress_timer.start()
            self.engine_process.start(sys.executable, ["-m", "memex_engine.run", str(path),
                                       "--install", "--confirm-disk", answers.target_disk_id])
        except Exception:
            self._engine_error()

    def _update_progress(self):
        key, idle = progress.engine_progress(self.engine_log, self.engine_started,
                                             offset=self.engine_log_offset)
        secs = int(time.time() - self.engine_started)
        mmss = f"{secs // 60:02d}:{secs % 60:02d}"
        self.version_label.setText(f"{t(self.lang, key)}\n{t(self.lang, 'progress_elapsed').format(mmss=mmss)}")
        stuck = progress.is_stuck(idle)
        self.stuck_label.setText(t(self.lang, "progress_stuck") if stuck else "")
        self.stuck_label.setVisible(stuck)

    def _cleanup_engine(self):
        self.progress_timer.stop()
        self.progress_bar.hide()
        self.stuck_label.hide()
        if self.install_session:
            self.install_session.cleanup()
            self.install_session = None
        self.next_btn.setEnabled(True)
        self.back_btn.setEnabled(True)
        self.stack.setEnabled(True)
        self.version_label.setText(PRODUCT_VERSION)

    def _engine_error(self, *_, code=ErrorCode.INSTALL_FAIL):
        self._cleanup_engine()
        msg = error_message(code, self.lang)
        QMessageBox.critical(self, msg["title"], f"{msg['body']}\n\n{msg['action']}\n({msg['code']})")

    @staticmethod
    def _engine_error_code(stderr: str) -> ErrorCode:
        """Specific code from the engine's stderr JSON (last JSON line); never shows raw text."""
        for line in reversed(stderr.strip().splitlines()):
            try:
                value = json.loads(line)["error"]["code"]
                return ErrorCode(value)
            except (ValueError, KeyError, TypeError):
                continue
        return ErrorCode.INSTALL_FAIL

    def _engine_finished(self, code, exit_status):
        raw = bytes(self.engine_process.readAllStandardOutput()).decode(errors="replace")
        err = bytes(self.engine_process.readAllStandardError()).decode(errors="replace")
        self._cleanup_engine()
        try:
            report = json.loads(raw)
        except ValueError:
            report = {}
        if code != 0 or report.get("status") != "os_installed" or not report.get("installed"):
            self._engine_error(code=self._engine_error_code(err))
            return
        self.next_btn.setEnabled(False)
        self.back_btn.setEnabled(False)
        self.stack.setEnabled(False)
        QMessageBox.information(self, t(self.lang, "reboot_title"),
                                t(self.lang, "reboot_body").format(username=self.username))
        self.version_label.setText(t(self.lang, "reboot_body").format(username=self.username))
        self.reboot_btn.show()

    def closeEvent(self, event):
        if self.engine_process and self.engine_process.state() != QProcess.ProcessState.NotRunning:
            event.ignore()
        else:
            super().closeEvent(event)
