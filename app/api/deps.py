from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import decode_access_token
from app.db.mongodb import get_database
from app.models.superadmin import SuperAdminOut

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/superadmin/auth/login")


def get_db() -> AsyncIOMotorDatabase:
    return get_database()


async def get_current_superadmin(
    token: str = Depends(oauth2_scheme),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SuperAdminOut:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        subject = decode_access_token(token)
    except (JWTError, ValueError):
        raise credentials_error

    if not ObjectId.is_valid(subject):
        raise credentials_error

    # is_superadmin filters inline (not just at login) so flipping a user's
    # flag off immediately invalidates any token they already hold. Both
    # is_active (archived) and is_enabled (deactivated) block access —
    # they're independent flags, but either one should revoke a session.
    admin = await db.superadmins.find_one({"_id": ObjectId(subject), "is_superadmin": True})
    if admin is None or not admin.get("is_active", True) or not admin.get("is_enabled", True):
        raise credentials_error

    return SuperAdminOut(
        id=str(admin["_id"]),
        email=admin["email"],
        full_name=admin["full_name"],
        is_active=admin["is_active"],
    )
