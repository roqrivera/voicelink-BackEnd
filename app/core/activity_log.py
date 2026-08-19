from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.history import ActivityAction


async def record_activity(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_name: str,
    action: ActivityAction,
    target_user_id: str,
    target_user_name: str,
    details: str | None = None,
) -> None:
    """Called from the Users screen's mutation endpoints (create/update/
    archive/restore/activate/deactivate) so every action taken there shows
    up in the Activity History timeline. Never raises — a logging failure
    should never roll back or break the action it's recording.
    """
    try:
        await db.activity_history.insert_one(
            {
                "actor_id": actor_id,
                "actor_name": actor_name,
                "action": action,
                "target_user_id": target_user_id,
                "target_user_name": target_user_name,
                "details": details,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        pass


async def record_tenant_activity(
    db: AsyncIOMotorDatabase,
    *,
    actor_id: str,
    actor_name: str,
    action: ActivityAction,
    target_tenant_id: str,
    target_tenant_name: str,
    details: str | None = None,
) -> None:
    """Same as `record_activity` above, but for the All Tenants screen's
    own mutation endpoints (create/update/archive/restore) — a separate
    collection/timeline from the Users screen's, so the two don't mix.
    Never raises — a logging failure should never roll back or break the
    action it's recording.
    """
    try:
        await db.tenant_activity_history.insert_one(
            {
                "actor_id": actor_id,
                "actor_name": actor_name,
                "action": action,
                "target_tenant_id": target_tenant_id,
                "target_tenant_name": target_tenant_name,
                "details": details,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        pass
