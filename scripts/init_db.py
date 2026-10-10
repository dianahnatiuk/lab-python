"""Ручне створення таблиць (застосунок робить це сам при старті)."""

import asyncio

from app.db.base import Base
from app.db.session import engine
from app.models import user  # noqa: F401  (реєстрація моделей)


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tables created")


if __name__ == "__main__":
    asyncio.run(main())
