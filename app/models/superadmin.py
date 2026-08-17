from pydantic import BaseModel, EmailStr, Field


class SuperAdminOut(BaseModel):
    """Shape of the authenticated caller returned by `get_current_superadmin`.

    There is no dedicated `superadmins` collection — a superadmin is just a
    `users` document (see app/models/user.py) with `is_superadmin: true` and
    a `hashed_password` set. This model only describes the safe subset of
    that document every endpoint's `current_admin` dependency gets back.
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
    pipeline (no SMTP configured in this backend), so the password is set
    directly here and must be shared with the new admin out of band.
    """

    full_name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)
