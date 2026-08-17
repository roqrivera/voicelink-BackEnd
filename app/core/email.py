import logging
import smtplib
from email.message import EmailMessage

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.encryption import decrypt_secret
from app.core.smtp import SmtpConnectionConfig, open_connection

logger = logging.getLogger(__name__)


async def get_active_smtp_config(db: AsyncIOMotorDatabase) -> SmtpConnectionConfig | None:
    """The superadmin-configured SMTP settings (see the `smtp-settings`
    endpoints), decrypted and ready to use — or `None` if nothing's been
    saved yet, or the saved password can't be decrypted (e.g. it was
    written under a previous `ENCRYPTION_KEY`). Callers should treat
    `None` as "fall back to the static env-based SMTP_* settings", not an
    error — those still work exactly as before for anyone who hasn't
    configured this yet.
    """
    doc = await db.smtp_settings.find_one({"is_delete": {"$ne": True}})
    if not doc or not doc.get("smtp_server") or not doc.get("smtp_username") or not doc.get("smtp_password"):
        return None

    try:
        password = decrypt_secret(doc["smtp_password"])
    except Exception:
        logger.warning("Saved SMTP password could not be decrypted — falling back to env-based SMTP settings.")
        return None

    return SmtpConnectionConfig(
        server=doc["smtp_server"],
        port=doc.get("smtp_port", 587),
        username=doc["smtp_username"],
        password=password,
        timeout=doc.get("smtp_timeout", 10),
        security=doc.get("smtp_security", ""),
        reply_to=doc.get("smtp_reply_to_mail", ""),
    )


def send_email(*, to_email: str, subject: str, body: str, smtp_config: SmtpConnectionConfig | None = None) -> None:
    """Sends a plain-text email, in order of preference:

    1. Via `smtp_config` (the superadmin-configured SMTP settings), if given.
    2. Via the static env-based `SMTP_*` settings, if `SMTP_HOST` is set.
    3. Logged instead of sent — the default out of the box, so
       forgot-password works in local dev with no mail setup at all.

    Synchronous on purpose: callers pass this to FastAPI's
    `BackgroundTasks`, which runs plain (non-async) callables in a thread
    pool automatically, so a slow/blocking SMTP conversation never holds up
    the request/response cycle. `smtp_config` must therefore already be
    resolved (see `get_active_smtp_config`) by the caller *before*
    scheduling this as a background task — this function does no async DB
    access itself.
    """
    message = EmailMessage()
    message["Subject"] = subject
    message["To"] = to_email
    message.set_content(body)

    if smtp_config is not None:
        message["From"] = f"{settings.SMTP_FROM_NAME} <{smtp_config.username}>"
        if smtp_config.reply_to:
            message["Reply-To"] = smtp_config.reply_to

        server = open_connection(smtp_config)
        try:
            server.send_message(message)
        finally:
            try:
                server.quit()
            except Exception:
                pass
        return

    if not settings.SMTP_HOST:
        # warning, not info: with no explicit logging config (none exists
        # in this app yet), Python's root logger only surfaces WARNING+ by
        # default — at info this line would silently never appear
        # anywhere, defeating the entire point of the fallback.
        logger.warning("SMTP not configured — logging email instead of sending.\nTo: %s\nSubject: %s\n\n%s", to_email, subject, body)
        return

    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)
