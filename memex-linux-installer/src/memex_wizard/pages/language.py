from PySide6.QtWidgets import QLabel, QRadioButton, QVBoxLayout, QWidget

from memex_installer.i18n_ui import t


class LanguagePage(QWidget):
    def __init__(self, wizard) -> None:
        super().__init__()
        self.wizard = wizard
        layout = QVBoxLayout(self)
        self.title = QLabel()
        layout.addWidget(self.title)
        self.en = QRadioButton("English")
        self.fr = QRadioButton("Français")
        self.en.setChecked(True)
        layout.addWidget(self.en)
        layout.addWidget(self.fr)
        layout.addStretch()
        self.en.toggled.connect(self._sync)

    def _sync(self) -> None:
        self.wizard.lang = "fr" if self.fr.isChecked() else "en"
        self.wizard.retranslate()

    def retranslate(self) -> None:
        self.title.setText(t(self.wizard.lang, "language_title"))

    def validate(self) -> bool:
        self._sync()
        return True
