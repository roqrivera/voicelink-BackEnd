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

    admin = await db.superadmins.find_one({"_id": ObjectId(subject)})
    if admin is None or not admin.get("is_active", True):
        raise credentials_error

    return SuperAdminOut(
        id=str(admin["_id"]),
        email=admin["email"],
        full_name=admin["full_name"],
        is_active=admin["is_active"],
    )
