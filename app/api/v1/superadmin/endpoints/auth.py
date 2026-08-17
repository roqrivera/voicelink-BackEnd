from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.core.security import create_access_token, verify_password
from app.models.superadmin import LoginRequest, SuperAdminOut, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncIOMotorDatabase = Depends(get_db)) -> TokenResponse:
    admin = await db.users.find_one({"email": payload.email, "is_superadmin": True})
    if not admin or not admin.get("hashed_password") or not verify_password(payload.password, admin["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not admin.get("is_active", True) or not admin.get("is_enabled", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = create_access_token(subject=str(admin["_id"]))
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=SuperAdminOut)
async def read_current_superadmin(
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> SuperAdminOut:
    return current_admin
