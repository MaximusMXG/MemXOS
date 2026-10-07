from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget
from html import escape

from memex_installer.i18n_ui import t


def _fmt_size(num: int) -> str:
    return f"{num / (1024**3):.0f} GB"


class ConfirmPage(QWidget):
    def __init__(self, wizard) -> None:
        super().__init__()
        self.wizard = wizard
        layout = QVBoxLayout(self)
        self.title = QLabel()
        layout.addWidget(self.title)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("font-size: 20px;")
        layout.addWidget(self.summary)
        self.dual_note = QLabel()
        self.dual_note.setWordWrap(True)
        self.dual_note.setStyleSheet("color: #b35900; font-weight: bold;")
        layout.addWidget(self.dual_note)
        self.erase_ack = QCheckBox()
        self.erase_ack.setStyleSheet("color: #b00020; font-weight: bold;")
        self.erase_ack.toggled.connect(lambda _: self.wizard._update_nav())
        layout.addWidget(self.erase_ack)
        self._ack_key = None
        layout.addStretch()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh()

    def _disk(self):
        return next((d for d in self.wizard.disks if d.id == self.wizard.selected_disk_id), None)

    def needs_erase_ack(self) -> bool:
        disk = self._disk()
        return bool(disk and disk.has_windows and self.wizard.mode.value == "linux_only")

    def can_install(self) -> bool:
        return not self.needs_erase_ack() or self.erase_ack.isChecked()

    def _refresh(self) -> None:
        disk = self._disk()
        key = (self.wizard.selected_disk_id, self.wizard.mode)
        if key != self._ack_key:
            self._ack_key = key
            self.erase_ack.setChecked(False)
        need = self.needs_erase_ack()
        self.erase_ack.setVisible(need)
        self.erase_ack.setText(t(self.wizard.lang, "win_erase_confirm"))
        dual = self.wizard.mode.value == "dual_boot"
        self.dual_note.setVisible(dual)
        if dual and disk:
            two = not disk.has_windows
            self.dual_note.setText(t(self.wizard.lang, "dual_two_summary" if two else "dual_summary").format(disk=disk.model))
        model = disk.model if disk else "?"
        size = _fmt_size(disk.size_bytes) if disk else "?"
        lang = self.wizard.lang
        mode = "linux_only" if self.wizard.mode.value == "linux_only" else "dual_boot"
        preset = {"half": "size_half", "100gb": "size_100", "all_leftover": "size_rest", "full_disk": "size_full"}[self.wizard.linux_size.value]
        self.summary.setText(
            f"<b>{escape(model)}</b><br><span style='font-size:32px'>{size}</span><br><br>"
            f"{t(lang, 'language_title')}: {'Français' if lang.startswith('fr') else 'English'}<br>"
            f"{t(lang, 'pc_type_title')}: {t(lang, self.wizard.profile.value)}<br>"
            f"{t(lang, mode)}<br>{t(lang, preset)}<br>"
            f"{t(lang, 'username')}: {escape(self.wizard.username)}"
        )

    def retranslate(self) -> None:
        self.title.setText(t(self.wizard.lang, "confirm_title"))
        self._refresh()

    def validate(self) -> bool:
        return True
