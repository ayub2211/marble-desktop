# src/ui/pages/users.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
    QLineEdit, QMessageBox, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.models import User
from src.db.auth_repo import create_user
from src.db.security import hash_password
from src.ui.app_state import AppState


class AddUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add User")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.username = QLineEdit()
        self.username.setPlaceholderText("e.g. ali, staff1, viewer01")

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Set password")

        self.role = QComboBox()
        self.role.addItems(["ADMIN", "STAFF", "VIEWER"])

        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        form.addRow("Role", self.role)

        layout.addLayout(form)

        btns = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Create")
        btns.addStretch()
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)
        layout.addLayout(btns)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.accept)

    @property
    def data(self):
        return {
            "username": (self.username.text() or "").strip(),
            "password": self.password.text() or "",
            "role": (self.role.currentText() or "VIEWER").upper(),
        }


class EditUserDialog(QDialog):
    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit User")
        self.setMinimumWidth(420)
        self._user = user

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.username = QLineEdit(user.username or "")
        self.username.setEnabled(False)  # username locked (safe)

        self.role = QComboBox()
        self.role.addItems(["ADMIN", "STAFF", "VIEWER"])
        # set current
        cur_role = (user.role or "VIEWER").upper()
        idx = self.role.findText(cur_role)
        self.role.setCurrentIndex(idx if idx >= 0 else 2)

        self.is_active = QCheckBox("Active")
        self.is_active.setChecked(bool(getattr(user, "is_active", True)))

        form.addRow("Username", self.username)
        form.addRow("Role", self.role)
        form.addRow("", self.is_active)

        layout.addLayout(form)

        btns = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Save")
        btns.addStretch()
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)
        layout.addLayout(btns)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.accept)

    @property
    def role_value(self):
        return (self.role.currentText() or "VIEWER").upper()

    @property
    def active_value(self):
        return bool(self.is_active.isChecked())


class ResetPasswordDialog(QDialog):
    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Reset Password — {username}")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.pass1 = QLineEdit()
        self.pass1.setEchoMode(QLineEdit.Password)
        self.pass1.setPlaceholderText("New password")

        self.pass2 = QLineEdit()
        self.pass2.setEchoMode(QLineEdit.Password)
        self.pass2.setPlaceholderText("Confirm new password")

        form.addRow("New Password", self.pass1)
        form.addRow("Confirm", self.pass2)
        layout.addLayout(form)

        btns = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Update")
        btns.addStretch()
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)
        layout.addLayout(btns)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.accept)

    @property
    def password(self):
        return self.pass1.text() or ""

    @property
    def password2(self):
        return self.pass2.text() or ""


class UsersPage(QWidget):
    """
    Admin-only Users Management:
      - Create user
      - Edit role + active
      - Reset password
    """
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title_row = QHBoxLayout()
        title = QLabel("Users")
        title.setStyleSheet("font-size:22px;font-weight:800;")

        self.add_btn = QPushButton("+ Add User")
        self.edit_btn = QPushButton("Edit")
        self.reset_btn = QPushButton("Reset Password")

        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.add_btn)
        title_row.addWidget(self.edit_btn)
        title_row.addWidget(self.reset_btn)
        layout.addLayout(title_row)

        self.info = QLabel("")
        self.info.setStyleSheet("color:#9a9a9a; margin-top:6px;")
        layout.addWidget(self.info)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Username", "Role", "Active", "Created"])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # events
        self.add_btn.clicked.connect(self.add_user)
        self.edit_btn.clicked.connect(self.edit_user)
        self.reset_btn.clicked.connect(self.reset_password)

        self.table.cellDoubleClicked.connect(lambda *_: self.edit_user())

        self.load_data()
        self.apply_permissions()

    def apply_permissions(self):
        is_admin = AppState.is_admin()

        self.add_btn.setEnabled(is_admin)
        self.edit_btn.setEnabled(is_admin)
        self.reset_btn.setEnabled(is_admin)

        if not is_admin:
            self.info.setText("Viewer/Staff can only view users. Login as ADMIN to manage accounts.")
        else:
            self.info.setText("Tip: Double click a row to edit user.")

    def load_data(self):
        self.table.setRowCount(0)
        with get_db() as db:
            users = db.query(User).order_by(User.id.desc()).all()

        for r, u in enumerate(users):
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(u.id)))
            self.table.setItem(r, 1, QTableWidgetItem(u.username or ""))
            self.table.setItem(r, 2, QTableWidgetItem((u.role or "VIEWER").upper()))
            self.table.setItem(r, 3, QTableWidgetItem("Yes" if getattr(u, "is_active", True) else "No"))
            self.table.setItem(r, 4, QTableWidgetItem(str(getattr(u, "created_at", "") or "")))

    def _selected_user_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        try:
            return int(self.table.item(row, 0).text())
        except Exception:
            return None

    def add_user(self):
        if not AppState.is_admin():
            QMessageBox.information(self, "Not allowed", "Only ADMIN can create users.")
            return

        dlg = AddUserDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        data = dlg.data
        if not data["username"]:
            QMessageBox.warning(self, "Missing", "Username is required.")
            return
        if not data["password"]:
            QMessageBox.warning(self, "Missing", "Password is required.")
            return

        try:
            with get_db() as db:
                create_user(db, data["username"], data["password"], data["role"])
            self.load_data()
            QMessageBox.information(self, "Created", "User created ✅")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create user:\n{e}")

    def edit_user(self):
        if not AppState.is_admin():
            QMessageBox.information(self, "Not allowed", "Only ADMIN can edit users.")
            return

        user_id = self._selected_user_id()
        if not user_id:
            QMessageBox.information(self, "Select", "Select a user row first.")
            return

        with get_db() as db:
            u = db.query(User).get(user_id)
            if not u:
                QMessageBox.warning(self, "Not found", "User not found.")
                return

            dlg = EditUserDialog(u, self)
            if dlg.exec() != QDialog.Accepted:
                return

            # block disabling your own admin account safety (optional)
            cur = getattr(AppState, "current_user", None)
            if cur and getattr(cur, "id", None) == u.id:
                # allow role change? usually no
                if dlg.role_value != (u.role or "").upper():
                    QMessageBox.warning(self, "Not allowed", "You cannot change your own role.")
                    return

            u.role = dlg.role_value
            u.is_active = dlg.active_value
            db.commit()

        self.load_data()
        QMessageBox.information(self, "Saved", "User updated ✅")

    def reset_password(self):
        if not AppState.is_admin():
            QMessageBox.information(self, "Not allowed", "Only ADMIN can reset passwords.")
            return

        user_id = self._selected_user_id()
        if not user_id:
            QMessageBox.information(self, "Select", "Select a user row first.")
            return

        with get_db() as db:
            u = db.query(User).get(user_id)
            if not u:
                QMessageBox.warning(self, "Not found", "User not found.")
                return

            dlg = ResetPasswordDialog(u.username or "", self)
            if dlg.exec() != QDialog.Accepted:
                return

            if not dlg.password or len(dlg.password) < 4:
                QMessageBox.warning(self, "Weak", "Password must be at least 4 characters.")
                return
            if dlg.password != dlg.password2:
                QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
                return

            u.password_hash = hash_password(dlg.password)
            db.commit()

        QMessageBox.information(self, "Updated", "Password updated ✅")
