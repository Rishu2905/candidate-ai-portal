import asyncpg
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class PostgresDB:
    pool: asyncpg.Pool = None

pg = PostgresDB()

async def connect_postgres():
    try:
        #print(f"Connecting to: {settings.POSTGRES_DSN}")
        pg.pool = await asyncpg.create_pool(
            dsn=settings.POSTGRES_DSN,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        # verify connection is alive
        async with pg.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        logger.info("PostgreSQL connected — pool ready (min=2, max=10)")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        raise

async def close_postgres():
    if pg.pool:
        await pg.pool.close()
        logger.info("PostgreSQL connection pool closed")

# query helpers — tools use these, never the raw pool
async def fetch(query: str, *args):
    async with pg.pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def fetchrow(query: str, *args):
    async with pg.pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def fetchval(query: str, *args):
    async with pg.pool.acquire() as conn:
        return await conn.fetchval(query, *args)

async def execute(query: str, *args):
    async with pg.pool.acquire() as conn:
        return await conn.execute(query, *args)

async def executemany(query: str, args_list: list):
    async with pg.pool.acquire() as conn:
        return await conn.executemany(query, args_list)