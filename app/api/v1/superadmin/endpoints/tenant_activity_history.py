import re
from datetime import timezone

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.models.history import PaginatedTenantActivityHistory, TenantActivityHistoryOut
from app.models.superadmin import SuperAdminOut

router = APIRouter()


def _doc_to_out(doc: dict) -> TenantActivityHistoryOut:
    return TenantActivityHistoryOut(
        id=str(doc["_id"]),
        actor_id=doc["actor_id"],
        actor_name=doc["actor_name"],
        action=doc["action"],
        target_tenant_id=doc["target_tenant_id"],
        target_tenant_name=doc["target_tenant_name"],
        details=doc.get("details"),
        created_at=doc["created_at"].replace(tzinfo=timezone.utc),
    )


@router.get("/", response_model=PaginatedTenantActivityHistory)
async def list_tenant_activity_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=1000),
    search: str | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> PaginatedTenantActivityHistory:
    query: dict = {}
    if search:
        pattern = re.compile(re.escape(search.strip()), re.IGNORECASE)
        query["$or"] = [
            {"actor_name": pattern},
            {"target_tenant_name": pattern},
            {"action": pattern},
            {"details": pattern},
        ]

    # Always newest-first — this is a timeline, not a sortable grid, so
    # there's no sort_by/sort_dir param to expose here.
    total = await db.tenant_activity_history.count_documents(query)
    skip = (page - 1) * page_size
    docs = (
        await db.tenant_activity_history.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
        .to_list(length=page_size)
    )

    return PaginatedTenantActivityHistory(items=[_doc_to_out(d) for d in docs], total=total, page=page, page_size=page_size)
