from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.models.superadmin import SuperAdminOut

router = APIRouter()


@router.get("/summary")
async def get_summary(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> dict:
    return {
        "tenants": await db.tenants.count_documents({}),
        "users": await db.superadmins.count_documents({}),
        "dids": await db.dids.count_documents({}),
        "sip_trunks": await db.sip_trunks.count_documents({}),
        "open_tickets": await db.tickets.count_documents({"status": "open"}),
    }
