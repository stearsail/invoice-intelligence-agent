import os
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlalchemy.ext.asyncio.session import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from dotenv import load_dotenv
from pathlib import Path


load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
if not POSTGRES_PASSWORD:
    raise RuntimeError("POSTGRES_PASSWORD is not set. Check .env file.")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST")
if not POSTGRES_HOST:
    raise RuntimeError("POSTGRES_HOST is not set. Check .env file.")

db_url = f"postgresql+psycopg://postgres:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:5432/invoice_ledger"
engine = create_async_engine(db_url, echo=True)
session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
