from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.core.request_info import client_ip, parse_user_agent, resolve_location
from app.core.security import create_access_token, verify_password
from app.models.superadmin import LoginRequest, SuperAdminOut, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncIOMotorDatabase = Depends(get_db)) -> TokenResponse:
    admin = await db.users.find_one({"email": payload.email, "is_superadmin": True})
    if not admin or not admin.get("hashed_password") or not verify_password(payload.password, admin["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not admin.get("is_active", True) or not admin.get("is_enabled", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = create_access_token(subject=str(admin["_id"]))

    # Best-effort — a hiccup recording this (or the geo-IP lookup timing
    # out) should never prevent an otherwise-successful login.
    try:
        ip = client_ip(request)
        device, browser = parse_user_agent(request.headers.get("user-agent"))
        location = await resolve_location(ip)
        await db.login_history.insert_one(
            {
                "user_id": str(admin["_id"]),
                "user_name": admin["full_name"],
                "user_email": admin["email"],
                "login_at": datetime.now(timezone.utc),
                "ip_address": ip,
                "device": device,
                "browser": browser,
                "location": location,
            }
        )
    except Exception:
        pass

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=SuperAdminOut)
async def read_current_superadmin(
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> SuperAdminOut:
    return current_admin
