# main.py
import sys
from PySide6.QtWidgets import QApplication

from src.db.session import get_db
from src.db.auth_repo import user_count
from src.ui.auth_dialogs import FirstRunAdminDialog, LoginDialog
from src.ui.app_state import AppState
from src.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # 1) First run admin create (if no users)
    with get_db() as db:
        cnt = user_count(db)

    if cnt == 0:
        fr = FirstRunAdminDialog()
        if fr.exec() != FirstRunAdminDialog.Accepted:
            return
        # created fr.user (admin), still go to login for consistency

    # 2) Login
    lg = LoginDialog()
    if lg.exec() != LoginDialog.Accepted:
        return

    AppState.current_user = lg.user

    # 3) Launch app
    w = MainWindow()
    w.apply_permissions()  # ✅ role-based UI
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
