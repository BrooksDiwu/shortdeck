
import json
import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import HTTPException, status

from ..config import settings
from ..game.table import Table, Board
from ..game.table_rules import TableRules
from ..game.deck import Deck
from ..game.betting import SidePot
from ..game.player import Player

logger = logging.getLogger(__name__)

# Lua script for safe lock release (only release if token matches)
UNLOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

TABLE_STATE_TTL = 86400  # 24 hours in seconds
LOG_MAX_LENGTH = 1000
class TableService:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def create_table(
        self,
        rules: TableRules,
        creator_id: str,
        creator: Player,
    ) -> Table:
        """Create a new table, persist to Redis, return the Table object."""
        redis = await self._get_redis()
        table_id = str(uuid.uuid4())

        # Give creator admin role
        creator.is_admin = True
        creator.seat = 0
        creator.stack = rules.big_blind * 100  # default 100 BB buy-in

        deck = Deck.build(rules.variant)
        table = Table(
            table_id=table_id,
            players={creator_id: creator},
            player_join_order=[creator_id],
            admin_id=creator_id,
            rules=rules,
            board=Board(),
            pot=0,
            side_pots=[],
            deck=deck,
            dealer_seat=0,
            current_action_seat=0,
            phase="waiting",
            hand_number=0,
            action_seq=0,
            pending_vote=None,
        )

        await self.save_table(table)

        # Also write metadata to a tables index for listing
        table_meta = {
            "table_id": table_id,
            "rules": rules.to_dict(),
            "status": "open",
            "created_at": datetime.utcnow().isoformat(),
        }
        await redis.hset("tables:index", table_id, json.dumps(table_meta))

        return table

    async def get_table(self, table_id: str) -> Table:
        """Read table snapshot from Redis."""
        redis = await self._get_redis()
        key = f"table:{table_id}:state"
        raw = await redis.get(key)
        if raw is None:
            raise KeyError(f"Table {table_id} not found in Redis")
        data = json.loads(raw)
        return Table.from_dict(data)

    async def save_table(self, table: Table) -> None:
        """Write table snapshot to Redis with TTL reset."""
        table.last_action_at = datetime.utcnow()
        redis = await self._get_redis()
        key = f"table:{table.table_id}:state"
        await redis.setex(key, TABLE_STATE_TTL, json.dumps(table.to_dict()))

        # Update index status
        meta_raw = await redis.hget("tables:index", table.table_id)
        if meta_raw:
            meta = json.loads(meta_raw)
            meta["status"] = "active" if table.phase not in ("waiting",) else "open"
            await redis.hset("tables:index", table.table_id, json.dumps(meta))

    async def list_tables(self) -> list[Table]:
        """List all tables from the index."""
        redis = await self._get_redis()
        all_meta = await redis.hgetall("tables:index")
        tables = []
        for table_id, meta_raw in all_meta.items():
            try:
                meta = json.loads(meta_raw)
                if meta.get("status") in ("open", "active"):
                    table = await self.get_table(table_id)
                    tables.append(table)
            except Exception:
                continue
        return tables

    async def append_event(self, table_id: str, event: dict) -> None:
        """Append event to table log and trim to last LOG_MAX_LENGTH entries."""
        redis = await self._get_redis()
        log_key = f"table:{table_id}:log"
        await redis.rpush(log_key, json.dumps(event))
        await redis.ltrim(log_key, -LOG_MAX_LENGTH, -1)

    async def get_actions_for_hand(self, table_id: str, hand_number: int) -> list[dict]:
        """Read the Redis event log and return all betting actions for the given hand number."""
        redis = await self._get_redis()
        log_key = f"table:{table_id}:log"
        raw_events = await redis.lrange(log_key, 0, -1)
        actions = []
        for raw in raw_events:
            try:
                event = json.loads(raw)
            except Exception:
                continue
            if event.get("hand") == hand_number and event.get("type") == "action":
                actions.append(event)
        return actions

    async def publish_event(self, table_id: str, event: dict) -> None:
        """Publish event to Redis pub/sub channel."""
        redis = await self._get_redis()
        channel = f"table_events:{table_id}"
        await redis.publish(channel, json.dumps(event))

    @asynccontextmanager
    async def acquire_lock(self, table_id: str) -> AsyncGenerator[None, None]:
        """
        Distributed lock via Redis SET NX PX.
        Raises HTTP 409 on acquire failure.
        Releases via Lua script to ensure token ownership.
        """
        redis = await self._get_redis()
        lock_key = f"table:{table_id}:lock"
        lock_token = str(uuid.uuid4())
        ttl_ms = 5000

        acquired = await redis.set(lock_key, lock_token, nx=True, px=ttl_ms)
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another action is in progress. Please retry shortly.",
            )

        try:
            yield
        finally:
            # Safe release: only delete if our token still owns the lock
            try:
                await redis.eval(UNLOCK_SCRIPT, 1, lock_key, lock_token)
            except Exception as exc:
                logger.warning(f"Lock release failed for {table_id}: {exc}")

    async def persist_hand(
        self,
        hand_id: str,
        actions: list[dict],
        results: dict[str, dict],
        table_id: str,
        hand_number: int,
        rules_snapshot: TableRules,
        started_at: datetime,
        ended_at: datetime,
    ) -> None:
        """Write completed hand data to PostgreSQL."""
        from ..models.db import AsyncSessionLocal, HandModel, ActionModel, HandResultModel, TableModel
        import json as _json

        async with AsyncSessionLocal() as db:
            async with db.begin():
                # Upsert table record
                from sqlalchemy import select
                result = await db.execute(
                    select(TableModel).where(TableModel.table_id == table_id)
                )
                table_record = result.scalar_one_or_none()
                if table_record is None:
                    table_record = TableModel(
                        table_id=table_id,
                        rules_json=_json.dumps(rules_snapshot.to_dict()),
                        status="active",
                    )
                    db.add(table_record)

                # Create hand record
                hand_record = HandModel(
                    hand_id=hand_id,
                    table_id=table_id,
                    hand_number=hand_number,
                    rules_snapshot_json=_json.dumps(rules_snapshot.to_dict()),
                    started_at=started_at,
                    ended_at=ended_at,
                )
                db.add(hand_record)

                # Create action records
                for action_data in actions:
                    action_record = ActionModel(
                        action_id=str(uuid.uuid4()),
                        hand_id=hand_id,
                        session_id=action_data["session_id"],
                        street=action_data["street"],
                        action_type=action_data["action"],
                        amount=action_data.get("amount", 0),
                        seq=action_data["seq"],
                        timestamp=datetime.fromisoformat(action_data["timestamp"]),
                    )
                    db.add(action_record)

                # Create result records
                for session_id, result_data in results.items():
                    result_record = HandResultModel(
                        hand_id=hand_id,
                        session_id=session_id,
                        hole_cards_json=_json.dumps(result_data.get("hole_cards", [])),
                        best_hand=result_data.get("best_hand", ""),
                        board=_json.dumps(result_data.get("board", [])),
                        amount_won=result_data.get("amount_won", 0),
                    )
                    db.add(result_record)

    async def persist_table_if_missing(self, table_id: str, rules_json: str) -> None:
        """Upsert a TableModel row so FK constraints on stack_transactions are satisfied."""
        from ..models.db import AsyncSessionLocal, TableModel
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(TableModel).where(TableModel.table_id == table_id)
                )
                if result.scalar_one_or_none() is None:
                    db.add(TableModel(
                        table_id=table_id,
                        rules_json=rules_json,
                        status="active",
                    ))

    async def persist_stack_transaction(
        self,
        table_id: str,
        session_id: str,
        transaction_type: str,
        amount: int,
    ) -> None:
        """Record a buy-in, rebuy, or buyout to PostgreSQL."""
        from ..models.db import AsyncSessionLocal, StackTransactionModel
        import json as _json

        async with AsyncSessionLocal() as db:
            async with db.begin():
                tx = StackTransactionModel(
                    transaction_id=str(uuid.uuid4()),
                    table_id=table_id,
                    session_id=session_id,
                    transaction_type=transaction_type,
                    amount=amount,
                    timestamp=datetime.utcnow(),
                )
                db.add(tx)
