from sqlmodel import SQLModel

from invoice_agent.db.engine import engine
from invoice_agent.db.models import LedgerEntry  # noqa: F401 — import registers the table on SQLModel.metadata

if __name__ == "__main__":
    SQLModel.metadata.create_all(engine)
    print("Tables created (or already present).")
