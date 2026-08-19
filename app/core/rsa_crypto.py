import base64
from functools import lru_cache

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.core.config import settings

# OAEP-SHA256 on both ends (the frontend's pointycastle OAEPEncoding is
# configured to match) — the modern, safe RSA padding scheme, unlike
# PKCS#1 v1.5 which is vulnerable to padding-oracle attacks.
_OAEP_PADDING = padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)


class RsaNotConfiguredError(Exception):
    """Raised when RSA_PRIVATE_KEY_PEM is blank — same "fail loudly, don't
    silently skip encryption" stance as BucketProvisioningError.
    """


@lru_cache
def _private_key() -> rsa.RSAPrivateKey:
    if not settings.RSA_PRIVATE_KEY_PEM:
        raise RsaNotConfiguredError("RSA_PRIVATE_KEY_PEM is not configured — set it to a PEM-encoded RSA private key.")
    key = serialization.load_pem_private_key(settings.RSA_PRIVATE_KEY_PEM.encode(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise RsaNotConfiguredError("RSA_PRIVATE_KEY_PEM does not decode to an RSA private key.")
    return key


def get_public_key_pem() -> str:
    """The public half of the configured keypair, served at
    `GET /auth/public-key` — safe to expose without authentication, since
    a public key is (by definition) not secret.
    """
    return (
        _private_key()
        .public_key()
        .public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


def decrypt_rsa(ciphertext_b64: str) -> str:
    """Decrypts one RSA-OAEP-SHA256-encrypted, base64-encoded value — the
    frontend encrypts current_password/new_password with the public key
    before sending them, so this is how the change-password endpoint gets
    the plaintext back. Raises ValueError on any failure (bad base64,
    wrong key, tampered/corrupt ciphertext) with a single generic message
    regardless of which — distinguishing them would open a padding-oracle
    side channel.
    """
    try:
        ciphertext = base64.b64decode(ciphertext_b64, validate=True)
        plaintext = _private_key().decrypt(ciphertext, _OAEP_PADDING)
        return plaintext.decode()
    except RsaNotConfiguredError:
        raise
    except Exception as exc:
        raise ValueError("Could not decrypt the request payload.") from exc
