import re
from datetime import timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.models.superadmin import SuperAdminOut
from app.models.tenant import PaginatedTenants, TenantOut, TenantStatusSummary

router = APIRouter()

SORTABLE_FIELDS = {"name", "plan", "user_count", "auth_method", "trunk_status", "mrr", "status"}
_STATUSES = ("Active", "Degraded", "Suspended", "Trial")


def _doc_to_out(doc: dict) -> TenantOut:
    return TenantOut(
        id=str(doc["_id"]),
        name=doc["name"],
        subdomain=doc["subdomain"],
        plan=doc["plan"],
        user_count=doc.get("user_count", 0),
        auth_method=doc["auth_method"],
        trunk_status=doc.get("trunk_status", "Not configured"),
        mrr=doc.get("mrr", 0),
        status=doc["status"],
        # Motor/PyMongo hands back a naive datetime even though this was
        # stored UTC-aware — reattach tzinfo before serializing.
        created_at=doc["created_at"].replace(tzinfo=timezone.utc),
    )


@router.get("/", response_model=PaginatedTenants)
async def list_tenants(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="name"),
    sort_dir: Literal["asc", "desc"] = Query(default="asc"),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None, description="Filter to one of Active/Degraded/Suspended/Trial"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> PaginatedTenants:
    query: dict = {}
    if status and status in _STATUSES:
        query["status"] = status

    if search:
        pattern = re.compile(re.escape(search.strip()), re.IGNORECASE)
        query["$or"] = [{"name": pattern}, {"subdomain": pattern}]

    sort_field = sort_by if sort_by in SORTABLE_FIELDS else "name"
    sort_direction = 1 if sort_dir == "asc" else -1

    total = await db.tenants.count_documents(query)
    skip = (page - 1) * page_size
    docs = (
        await db.tenants.find(query)
        .sort(sort_field, sort_direction)
        .skip(skip)
        .limit(page_size)
        .to_list(length=page_size)
    )

    return PaginatedTenants(items=[_doc_to_out(d) for d in docs], total=total, page=page, page_size=page_size)


@router.get("/status-summary", response_model=TenantStatusSummary)
async def tenant_status_summary(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> TenantStatusSummary:
    counts = {s: await db.tenants.count_documents({"status": s}) for s in _STATUSES}
    return TenantStatusSummary(
        active=counts["Active"],
        degraded=counts["Degraded"],
        suspended=counts["Suspended"],
        trial=counts["Trial"],
    )
