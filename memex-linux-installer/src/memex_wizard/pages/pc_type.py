from PySide6.QtWidgets import QLabel, QRadioButton, QVBoxLayout, QWidget

from memex_installer.i18n_ui import t
from memex_installer.models import ProfileId


class PcTypePage(QWidget):
    def __init__(self, wizard) -> None:
        super().__init__()
        self.wizard = wizard
        layout = QVBoxLayout(self)
        self.title = QLabel()
        layout.addWidget(self.title)
        self.home = QRadioButton()
        self.workstation = QRadioButton()
        self.gaming = QRadioButton()
        self.home.setChecked(True)
        for btn in (self.home, self.workstation, self.gaming):
            layout.addWidget(btn)
        layout.addStretch()

    def retranslate(self) -> None:
        self.title.setText(t(self.wizard.lang, "pc_type_title"))
        self.home.setText(t(self.wizard.lang, "home"))
        self.workstation.setText(t(self.wizard.lang, "workstation"))
        self.gaming.setText(t(self.wizard.lang, "gaming"))

    def validate(self) -> bool:
        if self.gaming.isChecked():
            self.wizard.profile = ProfileId.GAMING
        elif self.workstation.isChecked():
            self.wizard.profile = ProfileId.WORKSTATION
        else:
            self.wizard.profile = ProfileId.HOME
        return True
