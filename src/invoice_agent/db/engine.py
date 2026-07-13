import os
from sqlmodel import create_engine
from dotenv import load_dotenv
from pathlib import Path


load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
if not POSTGRES_PASSWORD:
    raise RuntimeError("POSTGRES_PASSWORD is not set. Check .env file.")

db_url = (
    f"postgresql+psycopg://postgres:{POSTGRES_PASSWORD}@localhost:5432/invoice_ledger"
)
engine = create_engine(db_url, echo=True)
