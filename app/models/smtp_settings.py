from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SmtpSettingsPayload(BaseModel):
    """Shared shape for both saving and verifying SMTP settings — `POST
    /verify` tests exactly what's in this payload (whether or not it's
    been saved yet), and on a successful test persists it the same way
    `PUT /` would.
    """

    smtp_server: str = Field(min_length=1)
    smtp_port: int = Field(gt=0, le=65535)
    smtp_username: str = Field(min_length=1)
    # Blank means "keep the currently saved password" — the stored value
    # is encrypted at rest and never sent back to the client, so this is
    # the only way a client can submit "no change" for a secret field.
    smtp_password: str = ""
    smtp_timeout: int = Field(gt=0, le=300)
    smtp_security: str = ""
    smtp_reply_to_mail: EmailStr


class SmtpSettingsOut(BaseModel):
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_timeout: int = 10
    smtp_security: str = ""
    smtp_reply_to_mail: str = ""
    # True only if a password has ever been saved — the encrypted value
    # itself is never sent back to the client.
    has_password: bool = False
    is_verified: bool = False
    last_verified_at: datetime | None = None
    updated_at: datetime | None = None


class SmtpVerifyResponse(BaseModel):
    success: bool
    message: str
