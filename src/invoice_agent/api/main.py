from fastapi import FastAPI
from invoice_agent.api.routers.extraction import router as extraction_router
from invoice_agent.api.routers.ledger import router as ledger_router
from contextlib import asynccontextmanager

# @asynccontextmanager
# async def lifespan(app: FastAPI):


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello!"}


app.include_router(extraction_router)
app.include_router(ledger_router)
