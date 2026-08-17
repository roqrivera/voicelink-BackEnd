from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.core.security import hash_password
from app.models.superadmin import SuperAdminCreate, SuperAdminOut

router = APIRouter()


@router.post("/", response_model=SuperAdminOut, status_code=status.HTTP_201_CREATED)
async def create_superadmin(
    payload: SuperAdminCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> SuperAdminOut:
    # Email uniqueness spans the whole users collection, tenant end-users
    # included — see app/api/v1/superadmin/endpoints/users.py.
    existing = await db.users.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")

    full_name = payload.full_name.strip()
    result = await db.users.insert_one(
        {
            "email": payload.email,
            "full_name": full_name,
            "hashed_password": hash_password(payload.password),
            "is_superadmin": True,
            "is_active": True,
            "is_enabled": True,
        }
    )
    return SuperAdminOut(id=str(result.inserted_id), email=payload.email, full_name=full_name, is_active=True)
