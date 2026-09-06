from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from memex_installer.i18n_ui import t
from memex_installer.models import Answers


class AccountPage(QWidget):
    def __init__(self, wizard) -> None:
        super().__init__()
        self.wizard = wizard
        layout = QVBoxLayout(self)
        self.title = QLabel()
        layout.addWidget(self.title)
        form = QFormLayout()
        self.display_name = QLineEdit()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password2 = QLineEdit()
        self.password2.setEchoMode(QLineEdit.EchoMode.Password)
        self.display_name_label = QLabel()
        self.username_label = QLabel()
        self.password_label = QLabel()
        self.password2_label = QLabel()
        form.addRow(self.display_name_label, self.display_name)
        form.addRow(self.username_label, self.username)
        form.addRow(self.password_label, self.password)
        form.addRow(self.password2_label, self.password2)
        layout.addLayout(form)
        self.error = QLabel()
        layout.addWidget(self.error)
        layout.addStretch()
        self.display_name.textChanged.connect(self._derive_username)

    def _derive_username(self, text: str) -> None:
        if not self.username.isModified():
            self.username.setText(Answers.username_from_display(text))

    def retranslate(self) -> None:
        self.title.setText(t(self.wizard.lang, "account_title"))
        self.display_name_label.setText(t(self.wizard.lang, "display_name"))
        self.username_label.setText(t(self.wizard.lang, "username"))
        self.password_label.setText(t(self.wizard.lang, "password"))
        self.password2_label.setText(t(self.wizard.lang, "password2"))

    def validate(self) -> bool:
        self.error.clear()
        if not self.display_name.text().strip():
            self.error.setText("Display name required")
            return False
        user = self.username.text().strip().lower()
        if not user or " " in user:
            self.error.setText("Username must be lowercase ASCII, no spaces")
            return False
        if not self.password.text() or self.password.text() != self.password2.text():
            self.error.setText("Passwords must match")
            return False
        self.wizard.display_name = self.display_name.text().strip()
        self.wizard.username = user
        self.wizard.password = self.password.text()
        return True
