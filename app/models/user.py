from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["owner", "admin", "member", "superadmin"]


class UserOut(BaseModel):
    """A row in the Users screen's datatable — by request, this now
    includes platform superadmin accounts alongside tenant end-users, shown
    and editable identically.

    Two independent boolean flags, deliberately kept separate:
    - `is_active`: the archive flag (archived == not active). Hides the row
      from the active list entirely (only visible via the Archived view).
      There is no hard delete in this system — this is reversible via
      restore. Also blocks login, since `get_current_superadmin` and the
      login endpoint both check this same field.
    - `is_enabled`: the Active/Inactive status shown in the UI. Toggling
      this does NOT move the row between the active/archived lists — the
      user stays visible right where they are. It does block login (same
      as archiving), since an "Inactive" account shouldn't be usable either.
    """

    id: str
    full_name: str
    email: str
    role: Role
    last_active_at: datetime | None = None
    is_active: bool = True
    is_enabled: bool = True


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr
    role: Role


class UserUpdate(BaseModel):
    """All fields optional — only the ones an admin actually edited are sent."""

    full_name: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    role: Role | None = None


class PaginatedUsers(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int
