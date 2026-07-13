from invoice_agent.db.engine import engine
from sqlmodel import SQLModel

SQLModel.metadata.create_all(engine)
