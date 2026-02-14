# src/ui/auth_dialogs.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QHBoxLayout, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.auth_repo import user_count, create_user, authenticate


class FirstRunAdminDialog(QDialog):
    """
    Opens only when no users exist.
    Creates the first ADMIN user.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("First Run - Create Admin")
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)

        title = QLabel("Create Admin Account")
        title.setStyleSheet("font-size:18px;font-weight:800;")
        lay.addWidget(title)

        hint = QLabel("No users found. Create the first Admin account to continue.")
        hint.setStyleSheet("color:#9a9a9a;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)

        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        form.addRow("Confirm", self.confirm)
        lay.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        self.create_btn = QPushButton("Create Admin")
        btns.addWidget(self.create_btn)
        lay.addLayout(btns)

        self.create_btn.clicked.connect(self.on_create)

        self._user = None

    @property
    def user(self):
        return self._user

    def on_create(self):
        u = (self.username.text() or "").strip()
        p = self.password.text() or ""
        c = self.confirm.text() or ""

        if not u:
            QMessageBox.warning(self, "Missing", "Username required.")
            return
        if len(p) < 4:
            QMessageBox.warning(self, "Weak", "Password must be at least 4 characters.")
            return
        if p != c:
            QMessageBox.warning(self, "Mismatch", "Password confirmation does not match.")
            return

        try:
            with get_db() as db:
                if user_count(db) > 0:
                    QMessageBox.information(self, "Info", "Users already exist. Use login.")
                    self.reject()
                    return
                self._user = create_user(db, u, p, role="ADMIN")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)

        title = QLabel("Login")
        title.setStyleSheet("font-size:18px;font-weight:800;")
        lay.addWidget(title)

        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        lay.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        self.login_btn = QPushButton("Login")
        btns.addWidget(self.login_btn)
        lay.addLayout(btns)

        self.login_btn.clicked.connect(self.on_login)

        self._user = None

    @property
    def user(self):
        return self._user

    def on_login(self):
        u = (self.username.text() or "").strip()
        p = self.password.text() or ""

        if not u or not p:
            QMessageBox.warning(self, "Missing", "Enter username and password.")
            return

        with get_db() as db:
            user = authenticate(db, u, p)

        if not user:
            QMessageBox.critical(self, "Invalid", "Wrong username or password.")
            return

        self._user = user
        self.accept()
