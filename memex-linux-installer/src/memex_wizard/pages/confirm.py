from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

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
        mode = self.wizard.mode.value
        self.summary.setText(
            f"<b>{model}</b><br><span style='font-size:32px'>{size}</span><br><br>"
            f"Language: {self.wizard.lang}<br>"
            f"Profile: {self.wizard.profile.value}<br>"
            f"Mode: {mode}<br>"
            f"Linux size: {self.wizard.linux_size.value}<br>"
            f"User: {self.wizard.username}"
        )

    def retranslate(self) -> None:
        self.title.setText(t(self.wizard.lang, "confirm_title"))
        self._refresh()

    def validate(self) -> bool:
        return True
