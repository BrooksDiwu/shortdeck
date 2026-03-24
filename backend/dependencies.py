
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models.db import AsyncSessionLocal
from .game.player import Player

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/sessions", auto_error=False)

# Module-level Redis pool (initialized on startup)
_redis_pool: aioredis.Redis | None = None
async def init_redis() -> None:
    """Initialize Redis connection pool. Called on app startup."""
    global _redis_pool
    _redis_pool = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
async def close_redis() -> None:
    """Close Redis connection pool. Called on app shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency: yields Redis client from pool."""
    if _redis_pool is None:
        # Fallback: create a connection if pool not initialized
        client = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()
    else:
        yield _redis_pool
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
async def get_current_session(token: str = Depends(oauth2_scheme)) -> Player:
    """FastAPI dependency: validates JWT and returns the current Player."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from .services.session_service import SessionService
    service = SessionService()
    try:
        session_id = await service.validate_token(token)
        player = await service.get_session(session_id)
        return player
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
