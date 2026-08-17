import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    subject = payload.get("sub")
    if subject is None:
        raise ValueError("Token missing subject")
    return subject


def generate_reset_token() -> str:
    """The raw, single-use password-reset token emailed to the user —
    high-entropy (256 bits) on its own, so unlike a password it needs no
    slow hashing scheme; see `hash_reset_token` for what's actually stored.
    """
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """Only this hash is stored on the user's document — never the raw
    token — so a database read (backup, dump, compromised replica) can't
    be used to reset someone's password. A plain SHA-256 digest is
    appropriate here (unlike `hash_password`'s bcrypt): the input is
    already a random 256-bit value, not a low-entropy human-chosen
    password, so there's nothing for a slow KDF to protect against.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
