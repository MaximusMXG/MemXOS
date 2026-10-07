"""Fullscreen completer GUI."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QTimer, QProcess, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from memex_completer import wifi
from memex_completer.state import SetupState
from memex_installer.errors import ErrorCode, error_message
from memex_installer.i18n_ui import t, UI


def _language() -> str:
    path = Path("/etc/memex/language")
    if path.exists():
        return path.read_text(encoding="utf-8").strip() or "en"
    return "en"


def ack_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "memex-setup-acknowledged"


def should_show(state: SetupState, ack: Path | None = None) -> bool:
    # Autostart runs every login; once setup is done and the success screen was dismissed, stay away.
    return not (state.is_complete() and (ack or ack_path()).exists())


def acknowledge(ack: Path | None = None) -> None:
    path = ack or ack_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok\n", encoding="utf-8")
    except OSError:
        pass


class WifiDialog(QDialog):
    done = Signal(str)  # "" on success, else error kind

    def __init__(self, lang: str, parent=None) -> None:
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(t(lang, "wifi_connect"))
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.itemSelectionChanged.connect(self._sync)
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw.setPlaceholderText(t(lang, "wifi_password"))
        self.pw.returnPressed.connect(self._connect)
        self.show_pw = QCheckBox(t(lang, "wifi_show"))
        self.show_pw.toggled.connect(
            lambda on: self.pw.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password)
        )
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        self.rescan_btn = QPushButton(t(lang, "wifi_rescan"))
        self.rescan_btn.clicked.connect(self.rescan)
        self.connect_btn = QPushButton(t(lang, "wifi_connect"))
        self.connect_btn.clicked.connect(self._connect)
        self.cancel_btn = QPushButton(t(lang, "wifi_cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        row = QHBoxLayout()
        for w in (self.rescan_btn, self.connect_btn, self.cancel_btn):
            row.addWidget(w)
        for w in (self.list, self.pw, self.show_pw, self.msg):
            lay.addWidget(w)
        lay.addLayout(row)
        self.done.connect(self._finished)
        self._nets: list[wifi.Network] = []
        self._sync()
        self.rescan()

    def _sync(self) -> None:
        row = self.list.currentRow()
        net = self._nets[row] if 0 <= row < len(self._nets) else None
        self.connect_btn.setEnabled(net is not None)
        self.pw.setEnabled(bool(net and net.secured))

    def rescan(self) -> None:
        try:
            self._nets = wifi.scan()
        except Exception:
            self._nets = []
        self.list.clear()
        for n in self._nets:
            lock = "🔒 " if n.secured else ""
            self.list.addItem(f"{wifi.bars(n.signal)}  {n.signal}%   {lock}{n.ssid}")
        self.msg.setText("" if self._nets else t(self.lang, "wifi_none"))
        self._sync()

    def _connect(self) -> None:
        row = self.list.currentRow()
        if not (0 <= row < len(self._nets)) or not self.connect_btn.isEnabled():
            return
        net = self._nets[row]
        password = self.pw.text() if net.secured else None
        for w in (self.connect_btn, self.rescan_btn, self.list, self.pw):
            w.setEnabled(False)
        self.msg.setText(t(self.lang, "wifi_connecting"))

        def work() -> None:
            try:
                wifi.connect(net.ssid, password)
                self.done.emit("")
            except wifi.WifiError as exc:
                self.done.emit(str(exc) or "generic")
            except Exception:
                self.done.emit("generic")

        threading.Thread(target=work, daemon=True).start()

    def _finished(self, kind: str) -> None:
        if not kind:
            self.pw.clear()
            self.accept()
            return
        for w in (self.rescan_btn, self.list):
            w.setEnabled(True)
        self.pw.setEnabled(True)
        self.connect_btn.setEnabled(True)
        key = {"wrong_password": "wifi_err_password", "not_found": "wifi_err_notfound"}.get(kind, "wifi_err_generic")
        self.msg.setText(t(self.lang, key))


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
        self.wifi_btn = QPushButton(t(self.lang, "wifi_connect"))
        self.wifi_btn.clicked.connect(self._wifi)
        self.wifi_btn.hide()
        self.netset_btn = QPushButton(t(self.lang, "wifi_settings"))
        self.netset_btn.clicked.connect(self._net_settings)
        self.netset_btn.hide()
        layout.addWidget(self.wifi_btn)
        layout.addWidget(self.netset_btn)
        self.restart_btn = QPushButton(t(self.lang, "restart_pc"))
        self.restart_btn.clicked.connect(lambda: self._control(["reboot"]))
        self.restart_btn.hide()
        self.done_btn = QPushButton(t(self.lang, "done"))
        self.done_btn.clicked.connect(self._done)
        self.done_btn.hide()
        layout.addWidget(self.restart_btn)
        layout.addWidget(self.done_btn)
        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    def _control(self, args):
        self.control = QProcess(self)
        self.control.finished.connect(self._control_finished)
        self.control.errorOccurred.connect(lambda *_: QMessageBox.critical(self, t(self.lang, "setup_title"), t(self.lang, "control_failed")))
        self.control.start("systemctl", args)
        self.retry_btn.hide()

    def _control_finished(self, code, _):
        if code != 0:
            QMessageBox.critical(self, t(self.lang, "setup_title"), t(self.lang, "control_failed"))
        self.refresh()

    def _done(self):
        acknowledge()
        self.close()

    def _wifi(self):
        if WifiDialog(self.lang, self).exec() == QDialog.DialogCode.Accepted:
            self._retry()

    def _net_settings(self):
        try:
            QProcess.startDetached("systemsettings", ["kcm_networkmanagement"])
        except Exception:
            pass

    def _show_net_buttons(self, on: bool) -> None:
        self.wifi_btn.setVisible(on and wifi.has_wifi())
        self.netset_btn.setVisible(on)

    def _retry(self):
        self._control(["restart", "memex-setup.service"])

    def refresh(self) -> None:
        self._show_net_buttons(False)
        self.restart_btn.hide()
        self.done_btn.hide()
        if self.state.is_complete():
            self.body.setText(t(self.lang, "setup_complete"))
            self.done_btn.show()
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
            self.body.setText(f"{msg['title']}\n\n{msg['body']}\n\n{t(self.lang, 'wifi_hint')}")
            self.retry_btn.hide()
            self._show_net_buttons(True)
            return

        if status.phase == "failed":
            msg = error_message(ErrorCode.STEP_FAIL, self.lang)
            self.body.setText(
                f"{msg['title']}\n\n{msg['body']}\n\n{status.message}\n\n{msg['action']}\n({status.error_code or msg['code']})"
            )
            self.retry_btn.show()
            self._show_net_buttons(status.error_code == ErrorCode.NO_NET.value)
            return

        if status.phase == "reboot_required":
            self.body.setText(t(self.lang, "setup_reboot"))
            self.restart_btn.show()
            self.retry_btn.hide()
            return

        self.body.setText(t(self.lang, "step_" + status.step) if "step_" + status.step in UI["en"] else status.step)
        self.retry_btn.hide()


def main(argv: list[str] | None = None) -> int:
    if not should_show(SetupState()):
        return 0
    app = QApplication(argv or sys.argv)
    window = CompleterWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
