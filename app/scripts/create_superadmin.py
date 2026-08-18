import asyncio
import sys

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.core.security import hash_password


async def create_superadmin(email: str, password: str, full_name: str) -> None:
    """Inserts a platform superadmin into the `superadmins` collection —
    the same collection tenant end-users live in, distinguished by
    `is_superadmin` and a `hashed_password` (tenant users have neither)."""
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]

    existing = await db.superadmins.find_one({"email": email})
    if existing:
        print(f"A user with email {email} already exists.")
        client.close()
        return

    await db.superadmins.insert_one(
        {
            "email": email,
            "full_name": full_name,
            "hashed_password": hash_password(password),
            "is_superadmin": True,
            "is_active": True,
        }
    )
    print(f"Superadmin {email} created successfully.")
    client.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python -m app.scripts.create_superadmin <email> <password> <full_name>")
        sys.exit(1)

    asyncio.run(create_superadmin(sys.argv[1], sys.argv[2], sys.argv[3]))
