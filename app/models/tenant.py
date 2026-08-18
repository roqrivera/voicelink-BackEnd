from datetime import datetime
from typing import Literal

from pydantic import BaseModel

TenantStatus = Literal["Active", "Degraded", "Suspended", "Trial"]
TrunkStatus = Literal["Online", "Flapping", "Offline", "Not configured"]


class TenantOut(BaseModel):
    """A row in the All Tenants screen's datatable."""

    id: str
    name: str
    subdomain: str
    plan: str
    user_count: int
    auth_method: str
    trunk_status: TrunkStatus
    mrr: int
    status: TenantStatus
    created_at: datetime


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
