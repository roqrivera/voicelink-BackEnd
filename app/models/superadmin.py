from datetime import datetime, timezone

from pydantic import BaseModel, EmailStr, Field

from app.models.common import MongoBaseModel, PyObjectId


class SuperAdminInDB(MongoBaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    email: EmailStr
    full_name: str
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SuperAdminOut(BaseModel):
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
