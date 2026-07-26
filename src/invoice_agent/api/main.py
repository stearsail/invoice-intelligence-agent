from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from invoice_agent import config
from invoice_agent.api.routers.extraction import router as extraction_router
from invoice_agent.api.routers.ledger import router as ledger_router
from contextlib import asynccontextmanager
from invoice_agent.logging_config import setup_logging
from arq import create_pool

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = await create_pool(
        RedisSettings(host=config.REDIS_HOST, port=config.REDIS_PORT)
    )
    app.state.redis = redis
    try:
        yield
    finally:
        await redis.close()


app = FastAPI(
    title="Invoice/Receipt OCR extraction pipeline", version="0.1.0", lifespan=lifespan
)

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
