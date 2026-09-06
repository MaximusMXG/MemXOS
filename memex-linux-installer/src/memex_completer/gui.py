"""Fullscreen completer GUI."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from memex_completer.state import SetupState
from memex_installer.errors import ErrorCode, error_message
from memex_installer.i18n_ui import t


def _language() -> str:
    path = Path("/etc/memex/language")
    if path.exists():
        return path.read_text(encoding="utf-8").strip() or "en"
    return "en"


class CompleterWindow(QMainWindow):
    def __init__(self, state: SetupState | None = None) -> None:
        super().__init__()
        self.state = state or SetupState()
        self.lang = _language()
        self.setWindowTitle(t(self.lang, "setup_title"))
        self.showFullScreen()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.title = QLabel(t(self.lang, "setup_title"))
        self.title.setStyleSheet("font-size: 28px; font-weight: bold;")
        self.body = QLabel("")
        self.body.setWordWrap(True)
        self.body.setStyleSheet("font-size: 18px;")
        self.retry_btn = QPushButton(t(self.lang, "retry"))
        self.retry_btn.clicked.connect(self._retry)
        self.retry_btn.hide()
        layout.addWidget(self.title)
        layout.addWidget(self.body)
        layout.addWidget(self.retry_btn)
        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    def _retry(self) -> None:
        self.state.request_retry()
        self.retry_btn.hide()

    def refresh(self) -> None:
        if self.state.is_complete():
            self.body.setText(t(self.lang, "setup_complete"))
            self.retry_btn.hide()
            return

        if self.state.is_stuck():
            msg = error_message(ErrorCode.STUCK, self.lang)
            status = self.state.read_status()
            step = status.step if status else ""
            self.body.setText(f"{msg['title']}\n\n{msg['body']}\n\n{step}\n\n{msg['action']}\n({msg['code']})")
            self.retry_btn.show()
            return

        status = self.state.read_status()
        if not status:
            self.body.setText("…")
            return

        if status.phase == "waiting_network":
            msg = error_message(ErrorCode.NO_NET, self.lang)
            self.body.setText(f"{msg['title']}\n\n{msg['body']}\n\n{msg['action']}")
            self.retry_btn.hide()
            return

        if status.phase == "failed":
            msg = error_message(ErrorCode.STEP_FAIL, self.lang)
            self.body.setText(
                f"{msg['title']}\n\n{msg['body']}\n\n{status.message}\n\n{msg['action']}\n({status.error_code or msg['code']})"
            )
            self.retry_btn.show()
            return

        self.body.setText(f"{status.step}\n\n{status.message}")
        self.retry_btn.hide()


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv or sys.argv)
    window = CompleterWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
