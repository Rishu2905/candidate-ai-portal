from fastapi import FastAPI
from contextlib import asynccontextmanager
from config.settings import settings
from db.mongo_client import connect_mongo, close_mongo
from db.postgres_client import connect_postgres, close_postgres
from routers.analysis_router import router as analysis_router
from routers.interview_router import router as interview_router
from routers.admin_router import router as admin_router
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await connect_mongo()
    await connect_postgres()

    # scheduler is optional — prototype works without it
    try:
        from scheduler.market_tool_scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")

    yield

    # shutdown
    try:
        from scheduler.market_tool_scheduler import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler stop error: {e}")

    await close_mongo()
    await close_postgres()


app = FastAPI(
    title="hraiportal-ai",
    debug=settings.DEBUG,
    lifespan=lifespan
)

app.include_router(analysis_router, prefix="/api/candidate")
app.include_router(interview_router, prefix="/api/candidate/interview")
app.include_router(admin_router, prefix="/admin")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "hraiportal-ai",
        "model": settings.GROQ_MODEL
    }