from .config import REDIS_DB, REDIS_HOST, REDIS_PORT

import redis
import asyncio


redis_connection = None
async def getRedisConnection() -> redis.Redis:
    global redis_connection
    if redis_connection is None:
        redis_connection = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    return redis_connection