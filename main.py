from fastapi import FastAPI
from contextlib import asynccontextmanager
from config.settings import settings
from db.mongo_client import connect_mongo, close_mongo
import logging

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await connect_mongo()
    yield
    # shutdown
    await close_mongo()

app = FastAPI(title="candidate-ai-portal",debug=settings.DEBUG,lifespan=lifespan)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": settings.GROQ_MODEL,
        "db": settings.MONGO_DB_NAME
    }