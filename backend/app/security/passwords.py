"""Password hashing and verification utilities."""

from passlib.context import CryptContext


password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """Hash a plain-text password securely."""
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password cannot exceed 72 UTF-8 bytes.")

    return password_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plain-text password against its stored hash."""
    if len(plain_password.encode("utf-8")) > 72:
        return False

    return password_context.verify(plain_password, password_hash)
