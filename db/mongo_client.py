from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class MongoDB:
    resume_client: AsyncIOMotorClient = None
    memory_client: AsyncIOMotorClient = None
    resume_db: AsyncIOMotorDatabase = None
    memory_db: AsyncIOMotorDatabase = None


mongo = MongoDB()


async def connect_mongo():
    try:
        # two separate clients — two separate clusters
        mongo.resume_client = AsyncIOMotorClient(settings.MONGO_RESUME_URI)
        mongo.memory_client = AsyncIOMotorClient(settings.MONGO_MEMORY_URI)

        mongo.resume_db = mongo.resume_client[settings.MONGO_RESUME_DB]
        mongo.memory_db = mongo.memory_client[settings.MONGO_MEMORY_DB]

        # ping both to verify both are alive
        await mongo.resume_client.admin.command("ping")
        logger.info(f"Resume DB connected — {settings.MONGO_RESUME_DB}")

        await mongo.memory_client.admin.command("ping")
        logger.info(f"Memory DB connected — {settings.MONGO_MEMORY_DB}")

    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        raise


async def close_mongo():
    if mongo.resume_client:
        mongo.resume_client.close()
        logger.info("Resume DB connection closed")

    if mongo.memory_client:
        mongo.memory_client.close()
        logger.info("Memory DB connection closed")


# ── collection accessors ──────────────────────────────────────────────────────

def get_document_content():
    """
    resumedata cluster.
    Written by Java after PDF parse.
    Read by skill_extraction_tool.
    """
    return mongo.resume_db["document_content"]


def get_analysis_content():
    """
    resumedata cluster.
    Written by orchestrator after pipeline completes.
    Read by analysis_router status endpoint.
    """
    return mongo.resume_db["analysis_content"]


def get_candidate_memory():
    """
    candidate-memory cluster.
    Written by orchestrator after every analysis run.
    Read by orchestrator before every new run.
    Long term memory — never deleted.
    """
    return mongo.memory_db["candidate_memory"]