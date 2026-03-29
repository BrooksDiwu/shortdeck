
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .dependencies import init_redis, close_redis
from .api import tables as tables_router
from .api import sessions as sessions_router
from .websocket import router as ws_router

logger = logging.getLogger(__name__)
async def _abandonment_cleanup_task() -> None:
    """
    Background task: periodically mark tables as abandoned if all players
    disconnected more than 10 minutes ago, and clean up Redis keys older than 24h.
    """
    import json
    import redis.asyncio as aioredis

    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )

    while True:
        try:
            await asyncio.sleep(60)  # run every minute
            now = datetime.utcnow()

            all_meta = await redis_client.hgetall("tables:index")
            for table_id, meta_raw in all_meta.items():
                try:
                    meta = json.loads(meta_raw)
                    if meta.get("status") == "abandoned":
                        # Check if older than 24h — delete Redis keys
                        abandoned_at_str = meta.get("abandoned_at")
                        if abandoned_at_str:
                            abandoned_at = datetime.fromisoformat(abandoned_at_str)
                            if now - abandoned_at > timedelta(minutes=15):
                                await redis_client.delete(f"table:{table_id}:state")
                                await redis_client.delete(f"table:{table_id}:log")
                                await redis_client.delete(f"table:{table_id}:lock")
                                await redis_client.hdel("tables:index", table_id)
                                logger.info(f"Cleaned up abandoned table {table_id}")
                        continue

                    if meta.get("status") not in ("open", "active"):
                        continue

                    # Check if all players are disconnected
                    state_raw = await redis_client.get(f"table:{table_id}:state")
                    if not state_raw:
                        continue

                    from .game.table import Table
                    table = Table.from_dict(json.loads(state_raw))

                    connected_players = [
                        p for p in table.players.values()
                        if p.status not in ("disconnected", "sitting_out")
                    ]

                    if connected_players:
                        continue

                    # No active players — check inactivity duration
                    last_action = table.last_action_at
                    if last_action and now - last_action > timedelta(minutes=5):
                        meta["status"] = "abandoned"
                        meta["abandoned_at"] = now.isoformat()
                        await redis_client.hset("tables:index", table_id, json.dumps(meta))
                        logger.info(f"Table {table_id} marked as abandoned (inactive for 5+ minutes)")

                except Exception as exc:
                    logger.warning(f"Abandonment check error for table {table_id}: {exc}")

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception(f"Abandonment cleanup task error: {exc}")
@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: connect to Redis, init DB, start background tasks."""
    logger.info("Starting up %s v%s", settings.PROJECT_NAME, settings.VERSION)

    # Initialize Redis connection pool
    await init_redis()

    # Initialize database (create tables for dev; use Alembic for prod)
    try:
        from .models.db import init_db
        await init_db()
        logger.info("Database initialized")
    except Exception as exc:
        logger.warning(f"DB initialization skipped (no DB available): {exc}")

    # Start background tasks
    cleanup_task = asyncio.create_task(_abandonment_cleanup_task())
    logger.info("Background cleanup task started")

    yield

    # Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    await close_redis()
    logger.info("Shutdown complete")
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST routers
    app.include_router(sessions_router.router, prefix=settings.API_V1_PREFIX)
    app.include_router(tables_router.router, prefix=settings.API_V1_PREFIX)

    # WebSocket router
    app.include_router(ws_router.router)

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "project": settings.PROJECT_NAME,
            "version": settings.VERSION,
        }

    return app
app = create_app()
