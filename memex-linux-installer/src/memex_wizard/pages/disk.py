from html import escape

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from memex_installer.errors import ErrorCode, error_message
from memex_installer.i18n_ui import t
from memex_installer.models import InstallMode, LinuxSizePreset


def _fmt_size(num: int) -> str:
    gb = num / (1024**3)
    return f"{gb:.0f} GB"


def confirm_dual_boot(parent, lang: str) -> bool:
    """Modal dual-boot warning; OK stays disabled until 'I understand' is ticked."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(t(lang, "dual_warn_title"))
    box = QVBoxLayout(dlg)
    items = t(lang, "dual_warn_items").split("|")
    body = QLabel("<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>")
    body.setWordWrap(True)
    body.setStyleSheet("color: #b35900;")
    box.addWidget(body)
    ack = QCheckBox(t(lang, "dual_warn_ack"))
    box.addWidget(ack)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
    ok.setEnabled(False)
    ack.toggled.connect(ok.setEnabled)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    box.addWidget(buttons)
    return dlg.exec() == QDialog.DialogCode.Accepted


class DiskPage(QWidget):
    def __init__(self, wizard) -> None:
        super().__init__()
        self.wizard = wizard
        layout = QVBoxLayout(self)
        self.title = QLabel()
        layout.addWidget(self.title)
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.windows_warning = QLabel()
        self.windows_warning.setWordWrap(True)
        self.windows_warning.setStyleSheet("color: #b00020; font-weight: bold; font-size: 16px;")
        self.windows_warning.hide()
        layout.addWidget(self.windows_warning)
        self.advanced = QCheckBox()
        layout.addWidget(self.advanced)
        self.advanced_box = QWidget()
        adv = QVBoxLayout(self.advanced_box)
        adv.setContentsMargins(0, 0, 0, 0)
        self.advanced_box.hide()
        layout.addWidget(self.advanced_box)
        self.linux_only = QRadioButton()
        self.dual_boot = QRadioButton()
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.linux_only)
        self.mode_group.addButton(self.dual_boot)
        self.linux_only.setChecked(True)
        adv.addWidget(self.linux_only)
        adv.addWidget(self.dual_boot)
        self.size_label = QLabel()
        adv.addWidget(self.size_label)
        self.size_half = QRadioButton()
        self.size_100 = QRadioButton()
        self.size_rest = QRadioButton()
        self.size_group = QButtonGroup(self)
        for btn in (self.size_half, self.size_100, self.size_rest):
            self.size_group.addButton(btn)
        self.size_100.setChecked(True)
        for btn in (self.size_half, self.size_100, self.size_rest):
            adv.addWidget(btn)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)
        layout.addStretch()
        self.list.currentItemChanged.connect(self._refresh_options)
        self.dual_boot.toggled.connect(self._on_dual_toggled)
        self.advanced.toggled.connect(self._on_advanced_toggled)

    def _ask_dual_boot(self) -> bool:
        return confirm_dual_boot(self, self.wizard.lang)

    def _on_advanced_toggled(self, on: bool) -> None:
        self.advanced_box.setVisible(on)
        if not on:
            self.linux_only.setChecked(True)
            self.size_100.setChecked(True)
        self._refresh_options()

    def _on_dual_toggled(self, on: bool) -> None:
        if on and not self._ask_dual_boot():
            self.linux_only.setChecked(True)  # Cancel reverts to Linux only
        self._refresh_options()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._populate()

    def _populate(self) -> None:
        current = self._selected_disk()
        selected_id = current.id if current else self.wizard.selected_disk_id
        self.list.clear()
        for disk in self.wizard.disks:
            if disk.is_usb:
                continue
            badge = f" [{t(self.wizard.lang, 'windows_badge')}]" if disk.has_windows else ""
            text = f"{disk.model} — {_fmt_size(disk.size_bytes)}{badge}"
            item = QListWidgetItem(text)
            item.setData(256, disk.id)  # Qt.UserRole
            self.list.addItem(item)
        if self.list.count():
            row = next((i for i in range(self.list.count())
                        if self.list.item(i).data(256) == selected_id), 0)
            self.list.setCurrentRow(row)
        self._refresh_options()

    def _selected_disk(self):
        item = self.list.currentItem()
        if not item:
            return None
        disk_id = item.data(256)
        return next((d for d in self.wizard.disks if d.id == disk_id), None)

    def _refresh_options(self) -> None:
        disk = self._selected_disk()
        same_disk = bool(disk and disk.has_windows and self.dual_boot.isChecked())
        for btn in (self.size_half, self.size_100, self.size_rest, self.size_label):
            btn.setVisible(same_disk)

        erase = bool(disk and disk.has_windows and not self.dual_boot.isChecked())
        self.windows_warning.setText(t(self.wizard.lang, "win_erase_warning"))
        self.windows_warning.setVisible(erase)

        self.warning.clear()
        if self.dual_boot.isChecked() and disk and not disk.has_windows:
            any_windows = any(d.has_windows for d in self.wizard.disks)
            if any_windows:
                msg = error_message(ErrorCode.TWO_DISK, self.wizard.lang)
                self.warning.setText(f"{msg['title']}: {msg['body']}")

    def retranslate(self) -> None:
        self.title.setText(t(self.wizard.lang, "disk_title"))
        self.linux_only.setText(t(self.wizard.lang, "linux_only"))
        self.dual_boot.setText(t(self.wizard.lang, "dual_boot"))
        self.advanced.setText(t(self.wizard.lang, "advanced_options"))
        self.size_half.setText(t(self.wizard.lang, "size_half"))
        self.size_100.setText(t(self.wizard.lang, "size_100"))
        self.size_rest.setText(t(self.wizard.lang, "size_rest"))
        self._populate()

    def validate(self) -> bool:
        disk = self._selected_disk()
        if not disk:
            return False
        self.wizard.selected_disk_id = disk.id
        self.wizard.mode = InstallMode.DUAL_BOOT if self.dual_boot.isChecked() else InstallMode.LINUX_ONLY
        if self.wizard.mode == InstallMode.LINUX_ONLY or (disk and not disk.has_windows):
            self.wizard.linux_size = LinuxSizePreset.FULL_DISK
        elif self.size_half.isChecked():
            self.wizard.linux_size = LinuxSizePreset.HALF
        elif self.size_rest.isChecked():
            self.wizard.linux_size = LinuxSizePreset.ALL_LEFTOVER
        else:
            self.wizard.linux_size = LinuxSizePreset.GB_100
        return True
