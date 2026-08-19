from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

TenantStatus = Literal["Active", "Degraded", "Suspended", "Trial"]
TrunkStatus = Literal["Online", "Flapping", "Offline", "Not configured"]

# The only plans the New/Edit Tenant wizard offers — kept in one place since
# both the wizard's dropdown and the server-side MRR calculation need the
# exact same tier names and pricing. Not user-editable; a new tier requires
# a code change on both ends, matching the reference design's fixed list.
PlanTier = Literal["Starter", "Pro", "Growth"]


class TenantOut(BaseModel):
    """A row in the All Tenants screen's datatable, and the shape returned
    for a single tenant (`GET /tenants/{id}`) used to pre-fill the Edit
    Tenant wizard.
    """

    id: str
    code: str
    bucket_name: str
    name: str
    subdomain: str
    industry: str | None = None
    timezone: str
    address: str
    city: str
    state: str
    zip_code: str
    country: str
    primary_contact_name: str
    primary_contact_phone: str
    billing_contact_name: str | None = None
    billing_contact_email: str | None = None
    plan: str
    user_count: int
    owner_name: str
    owner_email: str
    default_language: str
    auth_method: str
    enforce_2fa: bool
    messaging_enabled: bool
    webrtc_enabled: bool
    trunk_status: TrunkStatus
    mrr: int
    status: TenantStatus
    created_at: datetime

    # The archive flag — independent of `status` (Active/Degraded/
    # Suspended/Trial), same as PlatformUser.is_active vs is_enabled.
    # There is no hard delete for tenants; archiving just hides the row
    # from the active list, reversible via `POST /tenants/{id}/restore`.
    is_active: bool = True


class PaginatedTenants(BaseModel):
    items: list[TenantOut]
    total: int
    page: int
    page_size: int


class TenantStatusSummary(BaseModel):
    """Per-status counts backing the All Tenants screen's stat-card row."""

    active: int
    degraded: int
    suspended: int
    trial: int


class TenantCreate(BaseModel):
    """Payload for the 4-step New Tenant wizard's "Create tenant" submit —
    every field across all 3 data-entry steps (Identity, Plan & owner,
    Configuration; step 4 is read-only review).
    """

    # Step 1 — Identity
    name: str = Field(min_length=1)
    subdomain: str = Field(min_length=1)
    industry: str | None = None
    timezone: str = Field(min_length=1)
    address: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)
    zip_code: str = Field(min_length=1)
    country: str = Field(min_length=1)
    primary_contact_name: str = Field(min_length=1)
    primary_contact_phone: str = Field(min_length=1)
    billing_contact_name: str | None = None
    billing_contact_email: EmailStr | None = None

    # Step 2 — Plan & owner
    plan: PlanTier
    user_count: int = Field(ge=1)
    owner_name: str = Field(min_length=1)
    owner_email: EmailStr
    is_trial: bool = True
    send_welcome_email: bool = True

    # Step 3 — Configuration
    default_language: str = Field(min_length=1)
    auth_method: str = Field(min_length=1)
    enforce_2fa: bool = True
    messaging_enabled: bool = True
    webrtc_enabled: bool = True


class TenantUpdate(BaseModel):
    """All fields optional — only the ones an admin actually edited are
    sent. Deliberately excludes the creation-only fields (`owner_*`,
    `is_trial`, `send_welcome_email`) — those describe a one-time
    provisioning action, not ongoing tenant state, so the Edit Tenant
    wizard doesn't collect them again.
    """

    name: str | None = Field(default=None, min_length=1)
    subdomain: str | None = Field(default=None, min_length=1)
    industry: str | None = None
    timezone: str | None = Field(default=None, min_length=1)
    address: str | None = Field(default=None, min_length=1)
    city: str | None = Field(default=None, min_length=1)
    state: str | None = Field(default=None, min_length=1)
    zip_code: str | None = Field(default=None, min_length=1)
    country: str | None = Field(default=None, min_length=1)
    primary_contact_name: str | None = Field(default=None, min_length=1)
    primary_contact_phone: str | None = Field(default=None, min_length=1)
    billing_contact_name: str | None = None
    billing_contact_email: EmailStr | None = None
    plan: PlanTier | None = None
    user_count: int | None = Field(default=None, ge=1)
    default_language: str | None = Field(default=None, min_length=1)
    auth_method: str | None = Field(default=None, min_length=1)
    enforce_2fa: bool | None = None
    messaging_enabled: bool | None = None
    webrtc_enabled: bool | None = None
