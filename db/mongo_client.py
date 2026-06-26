from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None

mongo = MongoDB()

async def connect_mongo():
    try:
        mongo.client = AsyncIOMotorClient(settings.MONGO_URI)
        mongo.db = mongo.client[settings.MONGO_DB_NAME]
        # ping to verify connection is actually alive
        await mongo.client.admin.command("ping")
        logger.info(f"MongoDB connected — db: {settings.MONGO_DB_NAME}")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        raise

async def close_mongo():
    if mongo.client:
        mongo.client.close()
        logger.info("MongoDB connection closed")

# collection accessors — tools import these, never the raw client
def get_document_content():
    return mongo.db["document_content"]

def get_analysis_content():
    return mongo.db["analysis_content"]