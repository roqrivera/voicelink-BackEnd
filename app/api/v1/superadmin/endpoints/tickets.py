from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_superadmin, get_db
from app.models.superadmin import SuperAdminOut

router = APIRouter()


@router.get("/")
async def list_tickets(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_admin: SuperAdminOut = Depends(get_current_superadmin),
) -> list[dict]:
    tickets = await db.tickets.find().to_list(length=200)
    for ticket in tickets:
        ticket["_id"] = str(ticket["_id"])
    return tickets
