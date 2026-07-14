from fastapi import FastAPI
from invoice_agent.api.routers.extraction import router as extraction_router

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello!"}


app.include_router(extraction_router)
