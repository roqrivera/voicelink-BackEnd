import re
from datetime import timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.models.history import LoginHistoryOut, PaginatedLoginHistory
from app.models.superadmin import SuperAdminOut

router = APIRouter()

SORTABLE_FIELDS = {"user_name", "login_at"}


def _doc_to_out(doc: dict) -> LoginHistoryOut:
    return LoginHistoryOut(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        user_name=doc["user_name"],
        user_email=doc["user_email"],
        # Motor/PyMongo hands back a naive datetime even though this was
        # stored UTC-aware — reattach tzinfo before serializing.
        login_at=doc["login_at"].replace(tzinfo=timezone.utc),
        ip_address=doc["ip_address"],
        device=doc["device"],
        browser=doc["browser"],
        location=doc["location"],
    )


@router.get("/", response_model=PaginatedLoginHistory)
async def list_login_history(
    page: int = Query(default=1, ge=1),
    # Upper bound raised well past the UI's page-size options so the
    # frontend's Export can request every matching row in one call.
    page_size: int = Query(default=20, ge=1, le=1000),
    sort_by: str = Query(default="login_at"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    search: str | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> PaginatedLoginHistory:
    query: dict = {}
    if search:
        pattern = re.compile(re.escape(search.strip()), re.IGNORECASE)
        query["$or"] = [
            {"user_name": pattern},
            {"user_email": pattern},
            {"ip_address": pattern},
            {"location": pattern},
            {"device": pattern},
            {"browser": pattern},
        ]

    sort_field = sort_by if sort_by in SORTABLE_FIELDS else "login_at"
    sort_direction = 1 if sort_dir == "asc" else -1

    total = await db.login_history.count_documents(query)
    skip = (page - 1) * page_size
    docs = (
        await db.login_history.find(query)
        .sort(sort_field, sort_direction)
        .skip(skip)
        .limit(page_size)
        .to_list(length=page_size)
    )

    return PaginatedLoginHistory(items=[_doc_to_out(d) for d in docs], total=total, page=page, page_size=page_size)
