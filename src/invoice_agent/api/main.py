from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from invoice_agent.logging_config import setup_logging
from invoice_agent.api.routers.extraction import router as extraction_router
from invoice_agent.api.routers.ledger import router as ledger_router

setup_logging()

# @asynccontextmanager
# async def lifespan(app: FastAPI):


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Hello!"}


app.include_router(extraction_router)
app.include_router(ledger_router)
