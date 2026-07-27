import asyncio

from sqlmodel import SQLModel

from invoice_pipeline.db.engine import engine
from invoice_pipeline.db.models import Job, LedgerEntry  # noqa: F401 — import registers the tables on SQLModel.metadata


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print("Tables created (or already present).")


if __name__ == "__main__":
    asyncio.run(main())
