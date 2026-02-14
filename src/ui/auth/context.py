# src/ui/auth/context.py

from __future__ import annotations
from typing import Any, Optional

_current_user: Optional[dict[str, Any]] = None

def set_current_user(user: dict[str, Any] | None):
    global _current_user
    _current_user = user

def get_current_user() -> dict[str, Any] | None:
    return _current_user

def current_role() -> str:
    u = _current_user or {}
    return str(u.get("role") or "VIEWER").upper()

def is_admin() -> bool:
    return current_role() == "ADMIN"

def is_staff() -> bool:
    return current_role() in ("ADMIN", "STAFF")

def is_viewer() -> bool:
    return current_role() == "VIEWER"

# Permissions
def can_manage_users() -> bool:
    return is_admin()

def can_add_transactions() -> bool:
    # Purchases / Sales / Returns / Adjustments
    return is_staff()

def can_edit_items() -> bool:
    # Items add/edit/import
    return is_staff()

def can_export() -> bool:
    # everyone can export
    return True
