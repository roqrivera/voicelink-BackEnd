import re
from datetime import timezone

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.models.history import ActivityHistoryOut, PaginatedActivityHistory
from app.models.superadmin import SuperAdminOut

router = APIRouter()


def _doc_to_out(doc: dict) -> ActivityHistoryOut:
    return ActivityHistoryOut(
        id=str(doc["_id"]),
        actor_id=doc["actor_id"],
        actor_name=doc["actor_name"],
        action=doc["action"],
        target_user_id=doc["target_user_id"],
        target_user_name=doc["target_user_name"],
        details=doc.get("details"),
        created_at=doc["created_at"].replace(tzinfo=timezone.utc),
    )


@router.get("/", response_model=PaginatedActivityHistory)
async def list_activity_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=1000),
    search: str | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> PaginatedActivityHistory:
    query: dict = {}
    if search:
        pattern = re.compile(re.escape(search.strip()), re.IGNORECASE)
        query["$or"] = [
            {"actor_name": pattern},
            {"target_user_name": pattern},
            {"action": pattern},
            {"details": pattern},
        ]

    # Always newest-first — this is a timeline, not a sortable grid, so
    # there's no sort_by/sort_dir param to expose here.
    total = await db.activity_history.count_documents(query)
    skip = (page - 1) * page_size
    docs = (
        await db.activity_history.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
        .to_list(length=page_size)
    )

    return PaginatedActivityHistory(items=[_doc_to_out(d) for d in docs], total=total, page=page, page_size=page_size)
