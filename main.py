from fastapi import FastAPI
from contextlib import asynccontextmanager
from config.settings import settings
from db.mongo_client import connect_mongo, close_mongo
from db.postgres_client import connect_postgres, close_postgres
from scheduler.market_tool_scheduler import start_scheduler, stop_scheduler
from routers import analysis_router, interview_router, admin_router
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────────
    logger.info("Starting hraiportal-ai service...")
    await connect_mongo()
    await connect_postgres()
    start_scheduler()
    logger.info("All connections established. Service ready.")
    yield
    # ── shutdown ─────────────────────────────────────────────────
    logger.info("Shutting down hraiportal-ai service...")
    stop_scheduler()
    await close_mongo()
    await close_postgres()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="hraiportal-ai",
    description="AI microservice for candidate portal",
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan
)

# ── routers ───────────────────────────────────────────────────────
app.include_router(analysis_router.router, prefix="/ai")
app.include_router(interview_router.router, prefix="/ai")
app.include_router(admin_router.router, prefix="/admin")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "hraiportal-ai",
        "model": settings.GROQ_MODEL,
        "mongo_db": settings.MONGO_DB_NAME
    }