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
