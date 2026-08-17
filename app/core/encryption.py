from cryptography.fernet import Fernet

from app.core.config import settings

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_secret(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Raises `cryptography.fernet.InvalidToken` if `token` wasn't
    encrypted with this app's current `ENCRYPTION_KEY` — e.g. a value
    written under a previous key, or by a different service entirely.
    Callers should treat that as "this secret can't be used anymore", not
    let it crash the request.
    """
    return _fernet.decrypt(token.encode()).decode()
