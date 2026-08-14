from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.models.superadmin import SuperAdminOut

router = APIRouter()


@router.get("/")
async def list_sip_trunks(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> list[dict]:
    trunks = await db.sip_trunks.find().to_list(length=200)
    for trunk in trunks:
        trunk["_id"] = str(trunk["_id"])
    return trunks
