from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.core.config import settings
from app.core.email import get_active_smtp_config, send_email
from app.core.request_info import client_ip, parse_user_agent, resolve_location
from app.core.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.models.superadmin import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SuperAdminOut,
    TokenResponse,
)

router = APIRouter()

# Identical wording regardless of whether the email matched an account —
# a response that varied would let a caller enumerate valid superadmin
# addresses by trying them against this endpoint one at a time.
_FORGOT_PASSWORD_MESSAGE = "If an account exists for that email, a password reset link has been sent."
_INVALID_RESET_LINK = "This reset link is invalid or has expired."


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


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ForgotPasswordResponse:
    admin = await db.users.find_one({"email": payload.email, "is_superadmin": True})

    # Same scoping as /login (is_superadmin, is_active, is_enabled) — an
    # account that couldn't log in shouldn't be able to reset its way
    # around that. Falls straight through to the generic response either
    # way, so this check is invisible to the caller.
    if admin is not None and admin.get("is_active", True) and admin.get("is_enabled", True):
        raw_token = generate_reset_token()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

        await db.users.update_one(
            {"_id": admin["_id"]},
            {"$set": {"reset_token_hash": hash_reset_token(raw_token), "reset_token_expires_at": expires_at}},
        )

        reset_link = f"{settings.FRONTEND_RESET_PASSWORD_URL}?token={raw_token}"
        body = (
            f"Hi {admin.get('full_name', '')},\n\n"
            "We received a request to reset your VoiceLink Admin password. "
            f"This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes:\n\n"
            f"{reset_link}\n\n"
            "If you didn't request this, you can safely ignore this email — your password won't change."
        )
        # Resolved (and decrypted) here, in the async request handler, since
        # `send_email` runs as a background task in a thread pool and does
        # no async DB access itself. Falls back to the static env-based
        # SMTP_* settings when nothing's been configured via the SMTP
        # settings screen yet.
        smtp_config = await get_active_smtp_config(db)
        # BackgroundTasks so a slow/unreachable SMTP server can't turn a
        # password-reset request into a hung request.
        background_tasks.add_task(
            send_email,
            to_email=admin["email"],
            subject="Reset your VoiceLink Admin password",
            body=body,
            smtp_config=smtp_config,
        )

    return ForgotPasswordResponse(message=_FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncIOMotorDatabase = Depends(get_db)) -> ResetPasswordResponse:
    admin = await db.users.find_one({"reset_token_hash": hash_reset_token(payload.token), "is_superadmin": True})
    if admin is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_RESET_LINK)

    expires_at = admin.get("reset_token_expires_at")
    # Mongo round-trips datetimes as naive UTC (no tzinfo) even though they
    # were stored aware — reattach it before comparing, or this raises
    # instead of correctly treating a stale token as expired.
    if expires_at is None or expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_RESET_LINK)

    await db.users.update_one(
        {"_id": admin["_id"]},
        {
            "$set": {"hashed_password": hash_password(payload.new_password)},
            "$unset": {"reset_token_hash": "", "reset_token_expires_at": ""},
        },
    )

    return ResetPasswordResponse(message="Password reset successfully. You can now sign in.")
