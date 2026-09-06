from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
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
        layout.addStretch()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        disk = next((d for d in self.wizard.disks if d.id == self.wizard.selected_disk_id), None)
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
