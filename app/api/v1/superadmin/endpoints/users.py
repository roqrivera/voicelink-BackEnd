import re
from datetime import timezone
from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.core.activity_log import record_activity
from app.models.superadmin import SuperAdminOut
from app.models.user import PaginatedUsers, Role, UserCreate, UserOut, UserUpdate

router = APIRouter()

SORTABLE_FIELDS = {"full_name", "email", "role", "last_active_at"}


def _doc_to_user_out(doc: dict) -> UserOut:
    return UserOut(
        id=str(doc["_id"]),
        full_name=doc["full_name"],
        email=doc["email"],
        # Superadmin documents have no `role` field of their own (see
        # app/models/superadmin.py) — derive one so every row still has a
        # role to show/sort/tag by.
        role="superadmin" if doc.get("is_superadmin") else doc["role"],
        # Motor/PyMongo hands back naive datetimes even though these were
        # stored UTC-aware — reattach tzinfo so the serialized JSON carries
        # an explicit offset instead of a bare, ambiguous string.
        last_active_at=(doc["last_active_at"].replace(tzinfo=timezone.utc) if doc.get("last_active_at") else None),
        is_active=doc.get("is_active", True),
        is_enabled=doc.get("is_enabled", True),
    )


async def _get_user_or_404(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return doc


@router.get("/", response_model=PaginatedUsers)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="full_name"),
    sort_dir: Literal["asc", "desc"] = Query(default="asc"),
    search: str | None = Query(default=None),
    role: Role | None = Query(default=None),
    archived: bool = Query(default=False, description="False (default): active users. True: archived users."),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> PaginatedUsers:
    # Platform superadmin accounts live in this same collection and are
    # included here by request — role="superadmin" is derived, not a real
    # field on those documents, so it isn't filterable via `role` below.
    query: dict = {"is_active": not archived}

    if role is not None:
        query["role"] = role

    if search:
        pattern = re.compile(re.escape(search.strip()), re.IGNORECASE)
        query["$or"] = [
            {"full_name": pattern},
            {"email": pattern},
        ]

    sort_field = sort_by if sort_by in SORTABLE_FIELDS else "full_name"
    sort_direction = 1 if sort_dir == "asc" else -1

    total = await db.users.count_documents(query)
    skip = (page - 1) * page_size
    docs = await db.users.find(query).sort(sort_field, sort_direction).skip(skip).limit(page_size).to_list(length=page_size)

    return PaginatedUsers(
        items=[_doc_to_user_out(doc) for doc in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> UserOut:
    existing = await db.users.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")

    doc = {
        "full_name": payload.full_name.strip(),
        "email": payload.email,
        "role": payload.role,
        "last_active_at": None,
        "is_superadmin": False,
        "is_active": True,
        "is_enabled": True,
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id

    await record_activity(
        db,
        actor_id=current_admin.id,
        actor_name=current_admin.full_name,
        action="add",
        target_user_id=str(result.inserted_id),
        target_user_name=doc["full_name"],
        details=f"Role: {payload.role}",
    )
    return _doc_to_user_out(doc)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> UserOut:
    await _get_user_or_404(db, user_id)

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "full_name" in updates:
        updates["full_name"] = updates["full_name"].strip()

    if "email" in updates:
        conflict = await db.users.find_one({"email": updates["email"], "_id": {"$ne": ObjectId(user_id)}})
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")

    if updates:
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})

    doc = await db.users.find_one({"_id": ObjectId(user_id)})

    if updates:
        await record_activity(
            db,
            actor_id=current_admin.id,
            actor_name=current_admin.full_name,
            action="edit",
            target_user_id=user_id,
            target_user_name=doc["full_name"],
            details=f"Updated: {', '.join(sorted(updates))}",
        )
    return _doc_to_user_out(doc)


@router.post("/{user_id}/archive", response_model=UserOut)
async def archive_user(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> UserOut:
    """No hard delete in this system — this hides the user from the active
    list (and, for a superadmin row, immediately blocks their login, since
    `is_active` is the same field `get_current_superadmin` checks). Fully
    reversible via `restore_user` below.
    """
    if user_id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot archive your own account")

    existing = await _get_user_or_404(db, user_id)
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": False}})
    doc = await db.users.find_one({"_id": ObjectId(user_id)})

    await record_activity(
        db,
        actor_id=current_admin.id,
        actor_name=current_admin.full_name,
        action="archive",
        target_user_id=user_id,
        target_user_name=existing["full_name"],
    )
    return _doc_to_user_out(doc)


@router.post("/{user_id}/restore", response_model=UserOut)
async def restore_user(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> UserOut:
    # Unreachable in practice — an archived superadmin's token is already
    # rejected by get_current_superadmin, so they could never be the
    # `current_admin` calling this. Kept for defense in depth/symmetry with
    # the other three status-changing endpoints below.
    if user_id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot restore your own account")

    existing = await _get_user_or_404(db, user_id)
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": True}})
    doc = await db.users.find_one({"_id": ObjectId(user_id)})

    await record_activity(
        db,
        actor_id=current_admin.id,
        actor_name=current_admin.full_name,
        action="restore",
        target_user_id=user_id,
        target_user_name=existing["full_name"],
    )
    return _doc_to_user_out(doc)


@router.post("/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> UserOut:
    """Distinct from `archive_user` above — this only flips the Active/
    Inactive status shown in the UI. The row stays exactly where it is in
    the active/archived list (unlike archiving, which hides it). Blocks
    login the same way archiving does.
    """
    if user_id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot deactivate your own account")

    existing = await _get_user_or_404(db, user_id)
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_enabled": False}})
    doc = await db.users.find_one({"_id": ObjectId(user_id)})

    await record_activity(
        db,
        actor_id=current_admin.id,
        actor_name=current_admin.full_name,
        action="deactivate",
        target_user_id=user_id,
        target_user_name=existing["full_name"],
    )
    return _doc_to_user_out(doc)


@router.post("/{user_id}/activate", response_model=UserOut)
async def activate_user(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> UserOut:
    # Unreachable in practice — see restore_user's identical guard above.
    if user_id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot activate your own account")

    existing = await _get_user_or_404(db, user_id)
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_enabled": True}})
    doc = await db.users.find_one({"_id": ObjectId(user_id)})

    await record_activity(
        db,
        actor_id=current_admin.id,
        actor_name=current_admin.full_name,
        action="activate",
        target_user_id=user_id,
        target_user_name=existing["full_name"],
    )
    return _doc_to_user_out(doc)
