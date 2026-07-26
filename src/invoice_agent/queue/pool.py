from arq import ArqRedis
from fastapi import Request


async def get_redis_pool(request: Request) -> ArqRedis:
    return request.app.state.redis
