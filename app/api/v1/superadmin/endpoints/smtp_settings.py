from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_superadmin, get_db
from app.core.encryption import decrypt_secret, encrypt_secret
from app.core.smtp import SmtpConnectionConfig, open_connection
from app.models.smtp_settings import SmtpSettingsOut, SmtpSettingsPayload, SmtpVerifyResponse
from app.models.superadmin import SuperAdminOut

router = APIRouter()


async def _current_doc(db: AsyncIOMotorDatabase) -> dict | None:
    return await db.smtp_settings.find_one({"is_delete": {"$ne": True}})


def _to_out(doc: dict | None) -> SmtpSettingsOut:
    if doc is None:
        return SmtpSettingsOut()
    return SmtpSettingsOut(
        smtp_server=doc.get("smtp_server", ""),
        smtp_port=doc.get("smtp_port", 587),
        smtp_username=doc.get("smtp_username", ""),
        smtp_timeout=doc.get("smtp_timeout", 10),
        smtp_security=doc.get("smtp_security", ""),
        smtp_reply_to_mail=doc.get("smtp_reply_to_mail", ""),
        has_password=bool(doc.get("smtp_password")),
        is_verified=doc.get("is_verified", False),
        last_verified_at=doc.get("last_verified_at"),
        updated_at=doc.get("updated_at"),
    )


def _fields_from(payload: SmtpSettingsPayload) -> dict:
    return {
        "smtp_server": payload.smtp_server,
        "smtp_port": payload.smtp_port,
        "smtp_username": payload.smtp_username,
        "smtp_timeout": payload.smtp_timeout,
        "smtp_security": payload.smtp_security,
        "smtp_reply_to_mail": payload.smtp_reply_to_mail,
        "is_delete": False,
    }


async def _upsert(db: AsyncIOMotorDatabase, existing: dict | None, update: dict) -> dict:
    now = datetime.now(timezone.utc)
    if existing is None:
        update["created_at"] = now
        result = await db.smtp_settings.insert_one(update)
        return await db.smtp_settings.find_one({"_id": result.inserted_id})

    await db.smtp_settings.update_one({"_id": existing["_id"]}, {"$set": update})
    return await db.smtp_settings.find_one({"_id": existing["_id"]})


def _resolve_password(payload: SmtpSettingsPayload, existing: dict | None) -> str:
    """The password a connection attempt should actually use — either the
    freshly submitted one, or the existing encrypted value decrypted, if
    the form field was left blank to mean "keep the current password".
    """
    if payload.smtp_password:
        return payload.smtp_password

    stored = (existing or {}).get("smtp_password")
    if not stored:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SMTP password is required.")
    try:
        return decrypt_secret(stored)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The saved SMTP password can no longer be used — please re-enter it.",
        )


def _test_connection(payload: SmtpSettingsPayload, password: str) -> None:
    """Attempts a real SMTP connection + login; raises on any failure.
    Synchronous (smtplib has no async API) — callers must run this via
    `run_in_threadpool` so a slow/unreachable server doesn't block the
    event loop.
    """
    config = SmtpConnectionConfig(
        server=payload.smtp_server,
        port=payload.smtp_port,
        username=payload.smtp_username,
        password=password,
        timeout=payload.smtp_timeout,
        security=payload.smtp_security,
    )
    server = open_connection(config)
    try:
        server.quit()
    except Exception:
        pass


@router.get("/", response_model=SmtpSettingsOut)
async def get_smtp_settings(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> SmtpSettingsOut:
    return _to_out(await _current_doc(db))


@router.put("/", response_model=SmtpSettingsOut)
async def save_smtp_settings(
    payload: SmtpSettingsPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> SmtpSettingsOut:
    existing = await _current_doc(db)

    update = _fields_from(payload)
    update["updated_at"] = datetime.now(timezone.utc)
    # A save never implies the settings have been proven to work — only a
    # successful verify does. Resetting this here means an admin can't be
    # misled by a stale "Verified" badge after changing the config.
    update["is_verified"] = False
    update["last_verified_at"] = None
    if payload.smtp_password:
        update["smtp_password"] = encrypt_secret(payload.smtp_password)

    saved = await _upsert(db, existing, update)
    return _to_out(saved)


@router.post("/verify", response_model=SmtpVerifyResponse)
async def verify_smtp_settings(
    payload: SmtpSettingsPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> SmtpVerifyResponse:
    existing = await _current_doc(db)
    password = _resolve_password(payload, existing)

    try:
        await run_in_threadpool(_test_connection, payload, password)
    except HTTPException:
        raise
    except Exception as exc:
        return SmtpVerifyResponse(success=False, message=str(exc) or "Could not connect to the SMTP server.")

    # A successful test also saves — the common "test it, and if it works,
    # keep it" flow shouldn't require a separate Save click too. A failed
    # test never writes anything, so the last known-good saved config
    # stays intact.
    update = _fields_from(payload)
    now = datetime.now(timezone.utc)
    update["updated_at"] = now
    update["is_verified"] = True
    update["last_verified_at"] = now
    update["smtp_password"] = encrypt_secret(password)

    await _upsert(db, existing, update)

    return SmtpVerifyResponse(success=True, message="Connected and authenticated successfully.")
