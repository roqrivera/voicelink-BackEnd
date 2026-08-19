import re
import secrets
from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_superadmin, get_db
from app.core.config import settings
from app.core.email import get_active_smtp_config, send_email
from app.core.storage import BucketProvisioningError, create_tenant_bucket
from app.models.superadmin import SuperAdminOut
from app.models.tenant import (
    PaginatedTenants,
    TenantCreate,
    TenantOut,
    TenantStatusSummary,
    TenantUpdate,
)

router = APIRouter()

SORTABLE_FIELDS = {"name", "plan", "user_count", "auth_method", "trunk_status", "mrr", "status"}
_STATUSES = ("Active", "Degraded", "Suspended", "Trial")

# Base monthly price + price per seat for the 3 plan tiers the New/Edit
# Tenant wizard offers — mirrors the pricing shown in its Plan dropdown.
_PLAN_PRICING: dict[str, tuple[int, int]] = {
    "Starter": (99, 12),
    "Pro": (149, 22),
    "Growth": (249, 18),
}


def _doc_to_out(doc: dict) -> TenantOut:
    return TenantOut(
        id=str(doc["_id"]),
        code=doc["code"],
        bucket_name=doc["bucket_name"],
        name=doc["name"],
        subdomain=doc["subdomain"],
        industry=doc.get("industry"),
        timezone=doc["timezone"],
        address=doc["address"],
        city=doc["city"],
        state=doc["state"],
        zip_code=doc["zip_code"],
        country=doc["country"],
        primary_contact_name=doc["primary_contact_name"],
        primary_contact_phone=doc["primary_contact_phone"],
        billing_contact_name=doc.get("billing_contact_name"),
        billing_contact_email=doc.get("billing_contact_email"),
        plan=doc["plan"],
        user_count=doc.get("user_count", 0),
        owner_name=doc.get("owner_name", ""),
        owner_email=doc.get("owner_email", ""),
        default_language=doc.get("default_language", "English"),
        auth_method=doc["auth_method"],
        enforce_2fa=doc.get("enforce_2fa", True),
        messaging_enabled=doc.get("messaging_enabled", True),
        webrtc_enabled=doc.get("webrtc_enabled", True),
        trunk_status=doc.get("trunk_status", "Not configured"),
        mrr=doc.get("mrr", 0),
        status=doc["status"],
        # Motor/PyMongo hands back a naive datetime even though this was
        # stored UTC-aware — reattach tzinfo before serializing.
        created_at=doc["created_at"].replace(tzinfo=timezone.utc),
        is_active=doc.get("is_active", True),
    )


def _calculate_mrr(plan: str, user_count: int, is_trial: bool) -> int:
    """Trial tenants aren't billed yet — 0 MRR until they convert."""
    if is_trial:
        return 0
    base, per_user = _PLAN_PRICING.get(plan, (0, 0))
    return base + per_user * user_count


async def _generate_unique_code(db: AsyncIOMotorDatabase) -> str:
    """"vl-" plus 7 random digits (e.g. "vl-1234567") — this tenant's
    display code and its IONOS bucket name (see `create_tenant`).
    Collisions are astronomically unlikely (1 in 10 million) but checked
    and retried anyway rather than assumed away.
    """
    for _ in range(10):
        code = f"vl-{secrets.randbelow(10_000_000):07d}"
        if await db.tenants.find_one({"code": code}) is None:
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not generate a unique tenant code")


async def _get_tenant_or_404(db: AsyncIOMotorDatabase, tenant_id: str) -> dict:
    if not ObjectId.is_valid(tenant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    doc = await db.tenants.find_one({"_id": ObjectId(tenant_id)})
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return doc


@router.get("/", response_model=PaginatedTenants)
async def list_tenants(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="name"),
    sort_dir: Literal["asc", "desc"] = Query(default="asc"),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None, description="Filter to one of Active/Degraded/Suspended/Trial"),
    archived: bool = Query(default=False, description="False (default): active tenants. True: archived tenants."),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> PaginatedTenants:
    query: dict = {"is_active": not archived}
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
    # Matches list_tenants' default (non-archived) view — an archived
    # tenant shouldn't count toward the active dashboard stats.
    counts = {s: await db.tenants.count_documents({"status": s, "is_active": True}) for s in _STATUSES}
    return TenantStatusSummary(
        active=counts["Active"],
        degraded=counts["Degraded"],
        suspended=counts["Suspended"],
        trial=counts["Trial"],
    )


@router.post("/", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> TenantOut:
    existing = await db.tenants.find_one({"subdomain": payload.subdomain.strip()})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A tenant with this subdomain already exists")

    code = await _generate_unique_code(db)
    bucket_name = code

    # All-or-nothing: the tenant document is only created once its storage
    # bucket has actually been provisioned — a transient IONOS/network
    # issue should never leave behind a tenant with no working storage.
    try:
        await run_in_threadpool(create_tenant_bucket, bucket_name)
    except BucketProvisioningError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    doc = {
        "code": code,
        "bucket_name": bucket_name,
        "name": payload.name.strip(),
        "subdomain": payload.subdomain.strip(),
        "industry": payload.industry,
        "timezone": payload.timezone,
        "address": payload.address,
        "city": payload.city,
        "state": payload.state,
        "zip_code": payload.zip_code,
        "country": payload.country,
        "primary_contact_name": payload.primary_contact_name,
        "primary_contact_phone": payload.primary_contact_phone,
        "billing_contact_name": payload.billing_contact_name,
        "billing_contact_email": payload.billing_contact_email,
        "plan": payload.plan,
        "user_count": payload.user_count,
        "owner_name": payload.owner_name,
        "owner_email": payload.owner_email,
        "default_language": payload.default_language,
        "auth_method": payload.auth_method,
        "enforce_2fa": payload.enforce_2fa,
        "messaging_enabled": payload.messaging_enabled,
        "webrtc_enabled": payload.webrtc_enabled,
        "trunk_status": "Not configured",
        "mrr": _calculate_mrr(payload.plan, payload.user_count, payload.is_trial),
        "status": "Trial" if payload.is_trial else "Active",
        "created_at": now,
    }
    result = await db.tenants.insert_one(doc)
    doc["_id"] = result.inserted_id

    if payload.send_welcome_email:
        # Best-effort — unlike the bucket above, a failed welcome email
        # shouldn't undo an already-successfully-provisioned tenant.
        try:
            smtp_config = await get_active_smtp_config(db)
            body = (
                f"Hi {payload.owner_name},\n\n"
                f'Your VoiceLink workspace "{payload.name}" has been created. '
                "Our team will be in touch shortly to help you get set up.\n\n"
                "Welcome aboard!"
            )
            send_email(
                to_email=payload.owner_email,
                subject=f"Welcome to VoiceLink — {payload.name}",
                body=body,
                smtp_config=smtp_config,
            )
        except Exception:
            pass

    return _doc_to_out(doc)


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> TenantOut:
    doc = await _get_tenant_or_404(db, tenant_id)
    return _doc_to_out(doc)


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_tenant(
    tenant_id: str,
    payload: TenantUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> TenantOut:
    existing = await _get_tenant_or_404(db, tenant_id)

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}

    if "name" in updates:
        updates["name"] = updates["name"].strip()

    if "subdomain" in updates:
        updates["subdomain"] = updates["subdomain"].strip()
        conflict = await db.tenants.find_one({"subdomain": updates["subdomain"], "_id": {"$ne": existing["_id"]}})
        if conflict:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A tenant with this subdomain already exists")

    # Plan or seat-count changes recompute MRR — converting a trial tenant
    # to a paying one happens through the tenant's own status actions, not
    # this form, so its trial-ness here is just whatever is already saved.
    if "plan" in updates or "user_count" in updates:
        plan = updates.get("plan", existing["plan"])
        user_count = updates.get("user_count", existing.get("user_count", 0))
        is_trial = existing["status"] == "Trial"
        updates["mrr"] = _calculate_mrr(plan, user_count, is_trial)

    if updates:
        await db.tenants.update_one({"_id": existing["_id"]}, {"$set": updates})

    doc = await db.tenants.find_one({"_id": existing["_id"]})
    return _doc_to_out(doc)


@router.post("/{tenant_id}/archive", response_model=TenantOut)
async def archive_tenant(
    tenant_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> TenantOut:
    """No hard delete for tenants — this hides the tenant from the active
    list (`is_active=False`). Fully reversible via `restore_tenant` below.
    Independent of `status` (Active/Degraded/Suspended/Trial), same as
    PlatformUser's is_active vs is_enabled split.
    """
    await _get_tenant_or_404(db, tenant_id)
    await db.tenants.update_one({"_id": ObjectId(tenant_id)}, {"$set": {"is_active": False}})
    doc = await db.tenants.find_one({"_id": ObjectId(tenant_id)})
    return _doc_to_out(doc)


@router.post("/{tenant_id}/restore", response_model=TenantOut)
async def restore_tenant(
    tenant_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> TenantOut:
    await _get_tenant_or_404(db, tenant_id)
    await db.tenants.update_one({"_id": ObjectId(tenant_id)}, {"$set": {"is_active": True}})
    doc = await db.tenants.find_one({"_id": ObjectId(tenant_id)})
    return _doc_to_out(doc)
