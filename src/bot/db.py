from .config import DB

import asyncio
import asyncpg


async def connect():
    conn = await asyncpg.connect(
        user=DB['user'],
        password=DB['password'],
        database=DB['database'],
        host=DB['host']
    )

    return conn


asyncpg_errors = {
    'UniqueViolationError' : asyncpg.exceptions.UniqueViolationError,
}