from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db

router = APIRouter()


@router.get("/")
async def health_check(db: AsyncIOMotorDatabase = Depends(get_db)) -> dict:
    await db.command("ping")
    return {"status": "ok", "database": "connected"}
