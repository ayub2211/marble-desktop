# src/ui/app_state.py

class AppState:
    current_user = None  # SQLAlchemy User

    @classmethod
    def role(cls) -> str:
        if not cls.current_user:
            return "VIEWER"
        return (getattr(cls.current_user, "role", "VIEWER") or "VIEWER").upper()

    @classmethod
    def is_admin(cls) -> bool:
        return cls.role() == "ADMIN"

    @classmethod
    def is_staff(cls) -> bool:
        return cls.role() == "STAFF"

    @classmethod
    def is_viewer(cls) -> bool:
        return cls.role() == "VIEWER"

    @classmethod
    def can_add_transactions(cls) -> bool:
        # staff + admin can add sale/purchase/returns/adjustments
        return cls.is_admin() or cls.is_staff()

    @classmethod
    def can_edit_master_data(cls) -> bool:
        # items/locations etc (keep admin only)
        return cls.is_admin()
