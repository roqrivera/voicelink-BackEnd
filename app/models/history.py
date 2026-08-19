from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ActivityAction = Literal["add", "edit", "archive", "restore", "activate", "deactivate"]
LoginHistoryAction = Literal["Login", "Logout"]


class LoginHistoryOut(BaseModel):
    """One successful superadmin login or logout, recorded by the
    `/auth/login` and `/auth/logout` endpoints respectively. There is no
    failed-login tracking here — this is an activity record, not a
    security/brute-force monitor. `login_at` is the event's own timestamp
    for both kinds of row (kept as-is, rather than renamed, so existing
    sorting/filtering by this field keeps working unmodified) — `action`
    is what actually distinguishes a login from a logout.
    """

    id: str
    user_id: str
    user_name: str
    user_email: str
    login_at: datetime
    ip_address: str
    device: str
    browser: str
    location: str
    # Defaults to "Login" so rows written before this field existed still
    # deserialize correctly — every one of those actually was a login.
    action: LoginHistoryAction = "Login"


class PaginatedLoginHistory(BaseModel):
    items: list[LoginHistoryOut]
    total: int
    page: int
    page_size: int


class ActivityHistoryOut(BaseModel):
    """One user-management action taken by a superadmin (see
    app/core/activity_log.py) — Add/Edit/Archive/Restore/Activate/Deactivate
    on a row in the Users screen. `actor` is the superadmin who performed
    the action; `target` is the user record it was performed on.
    """

    id: str
    actor_id: str
    actor_name: str
    action: ActivityAction
    target_user_id: str
    target_user_name: str
    details: str | None = None
    created_at: datetime


class PaginatedActivityHistory(BaseModel):
    items: list[ActivityHistoryOut]
    total: int
    page: int
    page_size: int


class TenantActivityHistoryOut(BaseModel):
    """One tenant-management action taken by a superadmin (see
    app/core/activity_log.py) — Add/Edit/Archive/Restore on a row in the
    All Tenants screen. `actor` is the superadmin who performed the
    action; `target` is the tenant record it was performed on. A separate
    stream from `ActivityHistoryOut` (Users screen) rather than a shared
    one, since a tenant action has no equivalent to Activate/Deactivate.
    """

    id: str
    actor_id: str
    actor_name: str
    action: ActivityAction
    target_tenant_id: str
    target_tenant_name: str
    details: str | None = None
    created_at: datetime


class PaginatedTenantActivityHistory(BaseModel):
    items: list[TenantActivityHistoryOut]
    total: int
    page: int
    page_size: int
