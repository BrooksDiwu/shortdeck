
import asyncio
import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException

from ..services.session_service import SessionService
from ..services.table_service import TableService
from ..game.betting import BettingEngine
from .manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Grace period in seconds before auto-action on disconnect
DISCONNECT_GRACE_SECONDS = 30

# Active grace timers keyed by (table_id, session_id)
_grace_timers: dict[tuple[str, str], asyncio.Task] = {}


async def _grace_timer_task(
    table_id: str,
    session_id: str,
    table_service: TableService,
) -> None:
    """Wait DISCONNECT_GRACE_SECONDS then auto-act if it's the player's turn."""
    try:
        await asyncio.sleep(DISCONNECT_GRACE_SECONDS)
    except asyncio.CancelledError:
        return

    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if session_id not in table.players:
                return

            player = table.players[session_id]

            # Only auto-act if still disconnected AND it's their turn
            if player.status != "disconnected":
                return
            if table.current_action_seat != player.seat:
                return

            # Determine auto-action: check if legal, otherwise fold
            max_opponent_bet = max(
                (p.current_bet for sid, p in table.players.items()
                 if sid != session_id and p.status in ("active", "disconnected")),
                default=0,
            )
            if player.current_bet >= max_opponent_bet:
                auto_action = "check"
                auto_amount = 0
            else:
                auto_action = "fold"
                auto_amount = 0

            BettingEngine.apply_action(table, session_id, auto_action, auto_amount)
            table.action_seq += 1
            _advance_action(table)

            event_log = {
                "seq": table.action_seq,
                "hand": table.hand_number,
                "type": "action",
                "session_id": session_id,
                "street": table.phase,
                "action": auto_action,
                "amount": auto_amount,
                "auto": True,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await table_service.append_event(table_id, event_log)
            await table_service.save_table(table)

            broadcast_msg = _build_event_message(
                table, "action", session_id,
                action=auto_action,
                amount=auto_amount,
                auto=True,
                state_patch={
                    "pot": table.pot,
                    "current_action_seat": table.current_action_seat,
                    "players": {
                        sid: {"stack": p.stack, "current_bet": p.current_bet, "status": p.status}
                        for sid, p in table.players.items()
                    },
                },
            )
            await table_service.publish_event(table_id, broadcast_msg)

            logger.info(
                f"Auto-{auto_action} for disconnected player {session_id} "
                f"at table {table_id} (seat {player.seat})"
            )

    except Exception as exc:
        logger.exception(f"Grace timer error for {session_id} at table {table_id}: {exc}")
    finally:
        _grace_timers.pop((table_id, session_id), None)


def _build_state_snapshot(table, session_id: str) -> dict:
    """Build a full state snapshot message, hiding other players' hole cards."""
    players_public = []
    for sid, p in table.players.items():
        pd = p.to_dict()
        if sid != session_id:
            pd["hole_cards"] = []  # mask other players' hole cards
        players_public.append(pd)

    return {
        "type": "state_snapshot",
        "seq": table.action_seq,
        "hand": table.hand_number,
        "phase": table.phase,
        "board": table.board.to_dict(),
        "pot": table.pot,
        "side_pots": [sp.to_dict() for sp in table.side_pots],
        "players": players_public,
        "current_action_seat": table.current_action_seat,
        "rules": table.rules.to_dict(),
        "dealer_seat": table.dealer_seat,
    }
def _build_event_message(table, event_type: str, session_id: str, **kwargs) -> dict:
    """Build an incremental event broadcast message."""
    msg: dict = {
        "type": "event",
        "seq": table.action_seq,
        "hand": table.hand_number,
        "event": event_type,
        "session_id": session_id,
    }
    msg.update(kwargs)
    return msg
@router.websocket("/ws/table/{table_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    table_id: str,
    token: str = Query(...),
):
    # 1. Validate JWT before accepting connection
    try:
        session_service = SessionService()
        session_id = await session_service.validate_token(token)
    except Exception as exc:
        await websocket.close(code=4001, reason="Unauthorized: invalid or expired token")
        return

    table_service = TableService()

    # Verify table exists
    try:
        table = await table_service.get_table(table_id)
    except Exception:
        await websocket.close(code=4004, reason="Table not found")
        return

    # 2. Accept connection
    await manager.connect(table_id, session_id, websocket)

    # 3. Update player connection status
    async with table_service.acquire_lock(table_id):
        table = await table_service.get_table(table_id)
        if session_id in table.players:
            player = table.players[session_id]
            if player.status == "disconnected":
                player.status = "active"
                player.disconnect_at = None
                # Cancel any pending grace timer for this player
                timer_key = (table_id, session_id)
                timer_task = _grace_timers.pop(timer_key, None)
                if timer_task is not None:
                    timer_task.cancel()
                    logger.info(f"Cancelled grace timer for reconnected player {session_id} at table {table_id}")
        table.action_seq += 1
        await table_service.save_table(table)

    # 4. Send full state snapshot
    await manager.send_personal(table_id, session_id, _build_state_snapshot(table, session_id))

    # 5. Send private hole cards if mid-hand
    if session_id in table.players and table.phase not in ("waiting", "between_hands"):
        player = table.players[session_id]
        if player.hole_cards:
            await manager.send_personal(table_id, session_id, {
                "type": "deal",
                "seq": table.action_seq,
                "hand": table.hand_number,
                "hole_cards": [c.to_dict() for c in player.hole_cards],
            })

    # 6. Subscribe to Redis pub/sub and forward events to this client
    pubsub_task = asyncio.create_task(
        _subscribe_redis_events(table_id, session_id, websocket, table_service)
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "INVALID_JSON",
                    "message": "Message must be valid JSON",
                })
                continue

            msg_type = msg.get("type")

            if msg_type == "action":
                await _handle_action(table_id, session_id, msg, table_service)

            elif msg_type == "vote":
                await _handle_vote(table_id, session_id, msg, table_service)

            elif msg_type == "replay_request":
                from_seq = msg.get("from_seq", 0)
                await _handle_replay(table_id, session_id, from_seq, table_service)

            else:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "UNKNOWN_MESSAGE_TYPE",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        logger.info(f"Player {session_id} disconnected from table {table_id}")
    except Exception as exc:
        logger.exception(f"WebSocket error for {session_id} at table {table_id}: {exc}")
    finally:
        pubsub_task.cancel()
        manager.disconnect(table_id, session_id)
        await _handle_disconnect(table_id, session_id, table_service)
async def _subscribe_redis_events(
    table_id: str,
    session_id: str,
    websocket: WebSocket,
    table_service: TableService,
) -> None:
    """Subscribe to Redis pub/sub channel and forward events to this WebSocket."""
    try:
        redis = await table_service._get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"table_events:{table_id}")
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                try:
                    event = json.loads(data)
                    # Don't re-send to originator if it's their own action event
                    # (they already get the response inline)
                    if manager.is_connected(table_id, session_id):
                        await websocket.send_text(json.dumps(event))
                except Exception:
                    pass
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.exception(f"Pub/sub subscription error: {exc}")
async def _handle_action(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Handle a game action message under distributed lock."""
    action = msg.get("action")
    amount = int(msg.get("amount", 0))

    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            # Validate it's this player's turn
            if session_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_AT_TABLE",
                    "message": "You are not seated at this table",
                })
                return

            player = table.players[session_id]
            if table.current_action_seat != player.seat:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_YOUR_TURN",
                    "message": "It is not your turn to act",
                })
                return

            # Validate and apply action
            try:
                BettingEngine.validate_action(table, session_id, action, amount)
            except ValueError as exc:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "INVALID_ACTION",
                    "message": str(exc),
                })
                return

            BettingEngine.apply_action(table, session_id, action, amount)
            table.action_seq += 1

            # Advance action to next player
            _advance_action(table)

            # Persist state
            event_log = {
                "seq": table.action_seq,
                "hand": table.hand_number,
                "type": "action",
                "session_id": session_id,
                "street": table.phase,
                "action": action,
                "amount": amount,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await table_service.append_event(table_id, event_log)
            await table_service.save_table(table)

            # Broadcast event
            broadcast_msg = _build_event_message(
                table, "action", session_id,
                action=action,
                amount=amount,
                state_patch={
                    "pot": table.pot,
                    "current_action_seat": table.current_action_seat,
                    "players": {sid: {"stack": p.stack, "current_bet": p.current_bet, "status": p.status}
                                for sid, p in table.players.items()},
                },
            )
            await table_service.publish_event(table_id, broadcast_msg)

    except HTTPException as exc:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })
def _advance_action(table) -> None:
    """Move action to the next active player after an action."""
    seated = sorted(
        [p for p in table.players.values() if p.status == "active"],
        key=lambda p: p.seat,
    )
    if not seated:
        return
    current = table.current_action_seat
    after = [p for p in seated if p.seat > current]
    nxt = after[0] if after else seated[0]
    table.current_action_seat = nxt.seat
async def _handle_vote(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Handle a vote message."""
    vote = msg.get("vote")
    if vote not in ("for", "against"):
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "INVALID_VOTE",
            "message": "vote must be 'for' or 'against'",
        })
        return

    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)
            if table.pending_vote is None:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NO_ACTIVE_VOTE",
                    "message": "There is no active vote",
                })
                return

            if vote == "for":
                table.pending_vote.votes_for.add(session_id)
                table.pending_vote.votes_against.discard(session_id)
            else:
                table.pending_vote.votes_against.add(session_id)
                table.pending_vote.votes_for.discard(session_id)

            table.action_seq += 1
            await table_service.save_table(table)

            broadcast_msg = {
                "type": "event",
                "seq": table.action_seq,
                "hand": table.hand_number,
                "event": "vote",
                "session_id": session_id,
                "vote": vote,
                "votes_for": len(table.pending_vote.votes_for),
                "votes_against": len(table.pending_vote.votes_against),
            }
            await table_service.publish_event(table_id, broadcast_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })
async def _handle_replay(
    table_id: str,
    session_id: str,
    from_seq: int,
    table_service: TableService,
) -> None:
    """Replay events from the log starting at from_seq."""
    try:
        redis = await table_service._get_redis()
        log_key = f"table:{table_id}:log"
        raw_events = await redis.lrange(log_key, 0, -1)
        events = []
        for raw in raw_events:
            try:
                ev = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
                if ev.get("seq", 0) > from_seq:
                    events.append(ev)
            except Exception:
                pass

        for ev in events:
            await manager.send_personal(table_id, session_id, {
                "type": "replay",
                "event": ev,
            })
    except Exception as exc:
        logger.exception(f"Replay error: {exc}")
async def _handle_disconnect(
    table_id: str,
    session_id: str,
    table_service: TableService,
) -> None:
    """Mark player as disconnected, handle admin transfer."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if session_id not in table.players:
                return

            player = table.players[session_id]
            player.status = "disconnected"
            player.disconnect_at = datetime.utcnow()

            # Admin transfer: if disconnected player is admin, transfer immediately
            if table.admin_id == session_id:
                for joined_id in table.player_join_order:
                    if joined_id != session_id and joined_id in table.players:
                        other = table.players[joined_id]
                        if other.status != "disconnected":
                            table.admin_id = joined_id
                            other.is_admin = True
                            player.is_admin = False
                            break

            table.action_seq += 1
            await table_service.save_table(table)

            broadcast_msg = {
                "type": "event",
                "seq": table.action_seq,
                "hand": table.hand_number,
                "event": "player_disconnected",
                "session_id": session_id,
                "admin_id": table.admin_id,
            }
            await table_service.publish_event(table_id, broadcast_msg)

            # Start grace timer for auto-action
            timer_key = (table_id, session_id)
            # Cancel any existing timer (shouldn't happen, but be safe)
            old_timer = _grace_timers.pop(timer_key, None)
            if old_timer is not None:
                old_timer.cancel()
            _grace_timers[timer_key] = asyncio.create_task(
                _grace_timer_task(table_id, session_id, table_service)
            )
            logger.info(f"Started {DISCONNECT_GRACE_SECONDS}s grace timer for {session_id} at table {table_id}")

    except Exception as exc:
        logger.exception(f"Disconnect handling error: {exc}")
