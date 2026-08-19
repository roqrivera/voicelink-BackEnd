from pydantic import BaseModel, EmailStr, Field


class SuperAdminOut(BaseModel):
    """Shape of the authenticated caller returned by `get_current_superadmin`.

    The `superadmins` collection holds both platform superadmin accounts
    and tenant end-users (see app/models/user.py) — a superadmin is just a
    document in it with `is_superadmin: true` and a `hashed_password` set.
    This model only describes the safe subset of that document every
    endpoint's `current_admin` dependency gets back.
    """

    id: str
    email: EmailStr
    full_name: str
    is_active: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SuperAdminCreate(BaseModel):
    """Payload for inviting a new platform superadmin — grants full access
    to this admin portal itself, unlike `UserCreate` (app/models/user.py)
    which only ever creates a tenant end-user. There's no email-invite
    pipeline for account creation itself (see app/core/email.py for the
    separate forgot-password mail flow), so the password is set directly
    here and must be shared with the new admin out of band.
    """

    full_name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class ResetPasswordResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    """Unlike `ResetPasswordRequest` (no prior session, proven only by an
    emailed token), this is an authenticated superadmin changing their own
    password from within the app — proven by their current password
    instead.

    Both fields are RSA-OAEP-SHA256-encrypted (base64-encoded) with the
    public key from `GET /auth/public-key`, not plaintext — see
    app/core/rsa_crypto.py. The real min-length-8 check on the decrypted
    new_password happens in the endpoint itself, after decryption; the
    `min_length=1` here just rejects an empty/missing field.
    """

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class ChangePasswordResponse(BaseModel):
    message: str


class PublicKeyResponse(BaseModel):
    """The RSA public key (PEM) the frontend encrypts change-password
    payloads with — see app/core/rsa_crypto.py. Not secret; unauthenticated
    on purpose, the same way a JWKS endpoint would be.
    """

    public_key: str
