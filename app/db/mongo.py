"""Підключення до MongoDB (JSON-результати аналізів)."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import get_settings

settings = get_settings()
_client: AsyncIOMotorClient | None = None


async def connect() -> None:
    """Викликається при старті застосунку (клієнт прив'язується до робочого event loop)."""
    global _client
    _client = AsyncIOMotorClient(settings.mongo_url, serverSelectionTimeoutMS=5000)
    await results_collection().create_index("order_id", unique=True)


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def results_collection() -> AsyncIOMotorCollection:
    if _client is None:
        raise RuntimeError("MongoDB is not connected")
    return _client[settings.mongo_db]["results"]
