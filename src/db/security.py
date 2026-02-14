# src/db/security.py
import os
import hmac
import base64
import hashlib


def hash_password(password: str) -> str:
    """
    Returns: "pbkdf2$<salt_b64>$<hash_b64>"
    """
    password = (password or "").encode("utf-8")
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password, salt, 200_000, dklen=32)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        if not stored or not stored.startswith("pbkdf2$"):
            return False

        _, salt_b64, hash_b64 = stored.split("$", 2)
        salt = base64.b64decode(salt_b64.encode())
        expected = base64.b64decode(hash_b64.encode())

        dk = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, 200_000, dklen=32)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False
