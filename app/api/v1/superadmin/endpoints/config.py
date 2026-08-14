from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.models.superadmin import SuperAdminOut

router = APIRouter()


@router.get("/")
async def get_system_config(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> dict:
    config = await db.system_config.find_one({"_id": "global"})
    if config is None:
        return {}
    config["_id"] = str(config["_id"])
    return config
