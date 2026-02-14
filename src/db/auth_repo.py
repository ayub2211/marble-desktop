# src/db/auth_repo.py
from sqlalchemy.orm import Session

from src.db.models import User
from src.db.security import hash_password, verify_password


def user_count(db: Session) -> int:
    return db.query(User).count()


def create_user(db: Session, username: str, password: str, role: str = "ADMIN") -> User:
    username = (username or "").strip()
    if not username:
        raise ValueError("Username is required.")

    if db.query(User).filter(User.username == username).first():
        raise ValueError("Username already exists.")

    role = (role or "VIEWER").upper()
    if role not in ("ADMIN", "STAFF", "VIEWER"):
        role = "VIEWER"

    u = User(
        username=username,
        password_hash=hash_password(password or ""),
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def authenticate(db: Session, username: str, password: str) -> User | None:
    username = (username or "").strip()
    u = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not u:
        return None
    if not verify_password(password or "", u.password_hash):
        return None
    return u
