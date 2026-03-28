
import asyncio
import copy
import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException

from ..services.session_service import SessionService
from ..services.table_service import TableService
from ..game.betting import BettingEngine
from ..game.engine import GameEngine
from ..game.table import ModeVote
from ..game.table_rules import TableRules
from ..game.player import Player
from ..game.variants.holdem import HoldemVariant
from ..game.variants.shortdeck import ShortdeckVariant
from .manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Grace period in seconds before auto-action on disconnect
DISCONNECT_GRACE_SECONDS = 30

test = ""
# Active grace timers keyed by (table_id, session_id)
_grace_timers: dict[tuple[str, str], asyncio.Task] = {}


def _format_action_line(player_name: str, action: str, amount: int, auto: bool = False) -> str:
    prefix = f"{player_name}: "
    suffix = " (auto)" if auto else ""

    if action == "fold":
        return f"{prefix}folds{suffix}"
    if action == "check":
        return f"{prefix}checks{suffix}"
    if action == "call":
        return f"{prefix}calls {amount}{suffix}"
    if action == "raise":
        return f"{prefix}raises to {amount}{suffix}"
    if action == "all_in":
        return f"{prefix}is all-in for {amount}{suffix}"
    return f"{prefix}{action} {amount}{suffix}"


async def _grace_timer_task(
    table_id: str,
    session_id: str,
    table_service: TableService,
) -> None:
    """Wait DISCONNECT_GRACE_SECONDS, then fold the player and mark them sitting_out."""
    try:
        await asyncio.sleep(DISCONNECT_GRACE_SECONDS)
    except asyncio.CancelledError:
        return

    round_complete = False
    table = None

    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if session_id not in table.players:
                return

            player = table.players[session_id]

            if player.status != "disconnected":
                return

            is_their_turn = table.current_action_seat == player.seat

            if table.phase in ("waiting", "between_hands"):
                # No active hand — just sit them out
                player.status = "sitting_out"
                table.action_seq += 1
                await table_service.save_table(table)
                broadcast_msg = _build_event_message(
                    table, "player_sit_out", session_id,
                    players={session_id: {"status": "sitting_out"}},
                )
                await table_service.publish_event(table_id, broadcast_msg)
                logger.info(f"Disconnected player {session_id} sat out at table {table_id} (between hands)")
                return

            # Mid-hand: fold them out of the current hand.
            # sitting_out will be applied by end_hand() since disconnect_at is set.
            if is_their_turn:
                before_pot = table.pot
                BettingEngine.apply_action(table, session_id, "fold", 0)
                table.action_seq += 1
                put_in = max(0, table.pot - before_pot)
                table.current_hand_actions.append(
                    _format_action_line(player.name, "fold", put_in, auto=True)
                )

                _advance_action(table)
                round_complete = _is_betting_round_complete(table)

                event_log = {
                    "seq": table.action_seq,
                    "hand": table.hand_number,
                    "type": "action",
                    "session_id": session_id,
                    "street": table.phase,
                    "action": "fold",
                    "amount": 0,
                    "auto": True,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                await table_service.append_event(table_id, event_log)
            else:
                # Not their turn — fold them out-of-turn so they're removed from the hand.
                # Status stays "folded" until end_hand() transitions it to "sitting_out".
                player.status = "folded"
                table.action_seq += 1
                table.current_hand_actions.append(
                    _format_action_line(player.name, "fold", 0, auto=True)
                )
                round_complete = _is_betting_round_complete(table)

            await table_service.save_table(table)

            broadcast_msg = _build_event_message(
                table, "action", session_id,
                action="fold",
                amount=0,
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
                f"Auto-folded disconnected player {session_id} at table {table_id} "
                f"(seat {player.seat}, was_their_turn={is_their_turn})"
            )

        if round_complete:
            await _advance_street_or_showdown(table_id, session_id, table, table_service)

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
        "spectators": table.spectators,
        "pending_sit_requests": table.pending_sit_requests if session_id == table.admin_id else [],
        "is_paused": table.is_paused,
        "pause_requested_by": table.pause_requested_by,
        "pending_vote": table.pending_vote.to_dict() if table.pending_vote else None,
        "admin_id": table.admin_id,
        "player_join_order": table.player_join_order,
        "table_id": table.table_id,
        "hand_log": [entry.to_dict() for entry in table.hand_log],
    }


def _build_public_hand_complete_players(table) -> dict[str, dict]:
    latest_entry = table.hand_log[0] if table.hand_log else None
    shown_player_ids = {
        hand.session_id for hand in latest_entry.shown_hands
    } if latest_entry and latest_entry.showdown else set()

    players_patch: dict[str, dict] = {}
    for sid, player in table.players.items():
        is_shown = sid in shown_player_ids
        players_patch[sid] = {
            "stack": player.stack,
            "status": player.status,
            "hole_cards": [c.to_dict() for c in player.hole_cards] if is_shown else [],
            "is_revealed": [True] * len(player.hole_cards) if is_shown else [False] * len(player.hole_cards),
        }
    return players_patch


def _build_event_message(table, event_type: str, session_id: str, **kwargs) -> dict:
    """Build an incremental event broadcast message."""
    msg: dict = {
        "type": "event",
        "seq": table.action_seq,
        "hand": table.hand_number,
        "event_type": event_type,
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

    # 2. Resolve name uniqueness: check if a player with this name already exists in the table.
    # We do this before accepting the connection so we can reject cleanly.
    session_service = SessionService()
    try:
        connecting_player = await session_service.get_session(session_id)
        connecting_name = connecting_player.name
    except Exception:
        await websocket.close(code=4001, reason="Session not found")
        return

    # Find any seated player with the same name (case-insensitive)
    name_collision_id: str | None = None
    for pid, p in table.players.items():
        if p.name.lower() == connecting_name.lower() and pid != session_id:
            name_collision_id = pid
            break

    if name_collision_id is not None:
        colliding_player = table.players[name_collision_id]
        if colliding_player.status != "disconnected" and manager.is_connected(table_id, name_collision_id):
            # Name is taken by an active player — accept then immediately close so the
            # browser receives the close frame with our custom code and reason.
            await websocket.accept()
            await websocket.close(
                code=4003,
                reason=f"Name '{connecting_name}' is already taken by a connected player",
            )
            return
        # Disconnected player with same name: this connection takes over that slot.
        # We remap the session_id inside the table state.
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)
            # Re-check after acquiring lock
            if name_collision_id in table.players:
                old_player = table.players.pop(name_collision_id)
                old_player.session_id = session_id
                old_player.status = "active"
                old_player.disconnect_at = None
                table.players[session_id] = old_player

                # Update join order
                if name_collision_id in table.player_join_order:
                    idx = table.player_join_order.index(name_collision_id)
                    table.player_join_order[idx] = session_id

                # Transfer admin rights if needed
                if table.admin_id == name_collision_id:
                    table.admin_id = session_id
                    old_player.is_admin = True

                # Cancel grace timer for old session
                old_timer_key = (table_id, name_collision_id)
                old_timer_task = _grace_timers.pop(old_timer_key, None)
                if old_timer_task is not None:
                    old_timer_task.cancel()

                # Remove old session from spectators if present
                if name_collision_id in table.spectators:
                    table.spectators.remove(name_collision_id)

                table.action_seq += 1
                await table_service.save_table(table)
        # table now reflects the remapped state

        # Accept and continue as the remapped session_id
        await manager.connect(table_id, session_id, websocket)

        # Send full state snapshot and hole cards (reconnect path)
        await manager.send_personal(table_id, session_id, _build_state_snapshot(table, session_id))
        if table.phase not in ("waiting", "between_hands") and session_id in table.players:
            player = table.players[session_id]
            if player.hole_cards:
                await manager.send_personal(table_id, session_id, {
                    "type": "deal",
                    "seq": table.action_seq,
                    "hand": table.hand_number,
                    "hole_cards": [c.to_dict() for c in player.hole_cards],
                })

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
                await _dispatch_message(table_id, session_id, msg, table_service)
        except WebSocketDisconnect:
            logger.info(f"Player {session_id} (name-takeover) disconnected from table {table_id}")
        except Exception as exc:
            logger.exception(f"WebSocket error for {session_id} at table {table_id}: {exc}")
        finally:
            pubsub_task.cancel()
            manager.disconnect(table_id, session_id)
            await _handle_disconnect(table_id, session_id, table_service)
        return

    # 3. Accept connection
    await manager.connect(table_id, session_id, websocket)

    # 4. Update player connection status
    reconnect_broadcast = None
    async with table_service.acquire_lock(table_id):
        table = await table_service.get_table(table_id)
        changed = False
        if session_id in table.players:
            player = table.players[session_id]
            if player.status == "disconnected":
                # Mid-hand: restore to active so they can continue playing.
                # Between hands: sit them out so they must explicitly opt back in.
                new_status = "active" if table.phase not in ("waiting", "between_hands") else "sitting_out"
                player.status = new_status
                player.disconnect_at = None
                timer_key = (table_id, session_id)
                timer_task = _grace_timers.pop(timer_key, None)
                if timer_task is not None:
                    timer_task.cancel()
                    logger.info(f"Cancelled grace timer for reconnected player {session_id} at table {table_id}")
                changed = True
                table.action_seq += 1
                reconnect_broadcast = _build_event_message(
                    table, "player_reconnected", session_id,
                    players={session_id: {"status": new_status}},
                )
            if session_id in table.spectators:
                table.spectators.remove(session_id)
                changed = True
        else:
            if session_id not in table.spectators:
                if len(table.spectators) < 200:
                    table.spectators.append(session_id)
                    changed = True
        if changed:
            await table_service.save_table(table)
    if reconnect_broadcast is not None:
        await table_service.publish_event(table_id, reconnect_broadcast)

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
            await _dispatch_message(table_id, session_id, msg, table_service)

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
                if manager.is_connected(table_id, session_id):
                    try:
                        await websocket.send_text(data)
                    except Exception:
                        pass
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.exception(f"Pub/sub subscription error: {exc}")
async def _dispatch_message(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Route an incoming WebSocket message to the appropriate handler."""
    msg_type = msg.get("type")

    if msg_type == "action":
        await _handle_action(table_id, session_id, msg, table_service)
    elif msg_type == "vote":
        await _handle_vote(table_id, session_id, msg, table_service)
    elif msg_type == "replay_request":
        from_seq = msg.get("from_seq", 0)
        await _handle_replay(table_id, session_id, from_seq, table_service)
    elif msg_type == "propose_rule_change":
        await _handle_propose_rule_change(table_id, session_id, msg, table_service)
    elif msg_type == "force_rule_change":
        await _handle_force_rule_change(table_id, session_id, msg, table_service)
    elif msg_type == "pause_request":
        await _handle_pause_request(table_id, session_id, msg, table_service)
    elif msg_type == "unpause_request":
        await _handle_unpause_request(table_id, session_id, msg, table_service)
    elif msg_type == "reveal_card":
        await _handle_reveal_card(table_id, session_id, msg, table_service)
    elif msg_type == "rabbit_hunt_request":
        await _handle_rabbit_hunt_request(table_id, session_id, msg, table_service)
    elif msg_type == "sit_down_request":
        await _handle_sit_down_request(table_id, session_id, msg, table_service)
    elif msg_type == "approve_sit_down":
        await _handle_approve_sit_down(table_id, session_id, msg, table_service)
    elif msg_type == "reject_sit_down":
        await _handle_reject_sit_down(table_id, session_id, msg, table_service)
    elif msg_type == "stand_up":
        await _handle_stand_up(table_id, session_id, msg, table_service)
    elif msg_type == "sit_out":
        await _handle_sit_out(table_id, session_id, table_service)
    elif msg_type == "sit_in":
        await _handle_sit_in(table_id, session_id, table_service)
    elif msg_type == "host_stand_up":
        await _handle_host_stand_up(table_id, session_id, msg, table_service)
    elif msg_type == "host_remove_player":
        await _handle_host_remove_player(table_id, session_id, msg, table_service)
    elif msg_type == "start_hand":
        await _handle_start_hand(table_id, session_id, table_service)
    elif msg_type == "chat_message":
        await _handle_chat_message(table_id, session_id, msg, table_service)
    else:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "UNKNOWN_MESSAGE_TYPE",
            "message": f"Unknown message type: {msg_type}",
        })


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

            before_pot = table.pot
            BettingEngine.apply_action(table, session_id, action, amount)
            table.action_seq += 1
            put_in = max(0, table.pot - before_pot)
            action_amount = player.current_bet if action == "raise" else put_in
            table.current_hand_actions.append(
                _format_action_line(player.name, action, action_amount)
            )

            # Update last_aggressor_seat to track who opened/raised.
            # A raise/all_in resets the aggressor to the current player (everyone must act again).
            # A check sets the aggressor to the current player only if no aggressor yet,
            # so action goes around the table once before the street ends.
            if action in ("raise", "all_in"):
                table.last_aggressor_seat = player.seat
            elif action == "check" and table.last_aggressor_seat is None:
                table.last_aggressor_seat = player.seat

            # Advance action seat, then check if the round is complete.
            # Round is complete when the next player to act is the last aggressor
            # and all active bets are equal (everyone has acted and matched the bet).
            _advance_action(table)
            round_complete = _is_betting_round_complete(table)

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

        if round_complete:
            await _advance_street_or_showdown(table_id, session_id, table, table_service)

    except HTTPException as exc:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })
async def _handle_start_hand(
    table_id: str,
    session_id: str,
    table_service: TableService,
) -> None:
    """Admin starts a new hand from the waiting or between_hands phase."""
    round_complete = False
    table = None
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if session_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_SEATED",
                    "message": "Only seated players can start a hand",
                })
                return

            if table.phase not in ("waiting", "between_hands"):
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "INVALID_PHASE",
                    "message": "A hand is already in progress",
                })
                return

            active_players = [
                p for p in table.players.values()
                if p.status not in ("sitting_out", "disconnected")
            ]
            if len(active_players) < 2:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_ENOUGH_PLAYERS",
                    "message": "Need at least 2 players to start",
                })
                return

            variant = ShortdeckVariant() if table.rules.variant == "shortdeck" else HoldemVariant()
            engine = GameEngine(table, table.rules, variant)
            engine.start_hand()
            round_complete = _is_betting_round_complete(table)

            await table_service.save_table(table)

            # Broadcast new state snapshot (masks hole cards per player)
            for sid in list(table.players.keys()) + list(table.spectators):
                snap = _build_state_snapshot(table, sid)
                await manager.send_personal(table_id, sid, snap)

            # Send each player their private hole cards
            for sid, player in table.players.items():
                if player.hole_cards:
                    await manager.send_personal(table_id, sid, {
                        "type": "deal",
                        "seq": table.action_seq,
                        "hand": table.hand_number,
                        "hole_cards": [c.to_dict() for c in player.hole_cards],
                    })

            event_log = {
                "seq": table.action_seq,
                "hand": table.hand_number,
                "type": "start_hand",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await table_service.append_event(table_id, event_log)

        if round_complete:
            await _advance_street_or_showdown(table_id, session_id, table, table_service)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


def _is_betting_round_complete(table) -> bool:
    """Return True when all active players have matched the highest bet and acted.

    Called AFTER _advance_action, so current_action_seat points to the next player.
    The round is done when bets are all equal AND the next player to act is the
    last aggressor (meaning action has gone all the way around back to them).
    """
    # If only one non-folded player remains, hand is over immediately.
    # Disconnected players are still in the hand until they fold/auto-fold.
    non_folded = [p for p in table.players.values() if p.status in ("active", "all_in", "disconnected")]
    if len(non_folded) <= 1:
        return True

    active = [p for p in table.players.values() if p.status == "active"]
    if not active:
        return True
    max_bet = max(p.current_bet for p in active)
    if not all(p.current_bet == max_bet for p in active):
        return False
    # All bets are equal. If there's no aggressor recorded, treat as complete.
    # Otherwise, the round ends when current_action_seat cycles back to the last
    # aggressor. If the aggressor is no longer active (folded/all_in), bets being
    # equal is sufficient — nobody else needs to act.
    # NOTE: "disconnected" is NOT treated the same as folded/all_in here — a disconnected
    # player is still in the hand and their auto-action may not have run yet. We only
    # short-circuit if the aggressor is definitively out (folded or all_in).
    if table.last_aggressor_seat is None:
        return True
    active_seats = {p.seat for p in active}
    aggressor_player = next(
        (p for p in table.players.values() if p.seat == table.last_aggressor_seat), None
    )
    aggressor_out = aggressor_player is None or aggressor_player.status in ("folded", "all_in")
    if aggressor_out:
        return True
    if table.last_aggressor_seat not in active_seats:
        # Aggressor is disconnected. Round is complete only if they have already acted
        # (their current_bet matches the max bet, meaning their auto-action ran).
        # If they haven't acted yet, their grace timer will fire and advance action normally.
        return aggressor_player.current_bet == max_bet
    return table.current_action_seat == table.last_aggressor_seat


def _should_auto_runout(table) -> bool:
    """True when all remaining contenders are all-in except at most one active player."""
    live_contenders = [p for p in table.players.values() if p.status in ("active", "all_in")]
    if len(live_contenders) <= 1:
        return False
    active_count = sum(1 for p in live_contenders if p.status == "active")
    return active_count <= 1


def _advance_action(table) -> None:
    """Move action to the next active player after an action."""
    active = sorted(
        [p for p in table.players.values() if p.status == "active"],
        key=lambda p: p.seat,
    )
    if not active:
        return
    current = table.current_action_seat
    after = [p for p in active if p.seat > current]
    nxt = after[0] if after else active[0]
    table.current_action_seat = nxt.seat


async def _advance_street_or_showdown(
    table_id: str,
    session_id: str,
    table,
    table_service: TableService,
) -> None:
    """Deal the next street, or run showdown/end_hand if no streets remain."""
    variant = ShortdeckVariant() if table.rules.variant == "shortdeck" else HoldemVariant()
    engine = GameEngine(table, table.rules, variant)
    streets = engine.build_streets()  # [flop, turn, river]

    street_order = ["preflop", "flop", "turn", "river"]
    current_idx = street_order.index(table.phase) if table.phase in street_order else -1

    def _next_street(after_idx: int):
        for sc in streets:
            sc_idx = street_order.index(sc.name) if sc.name in street_order else -1
            if sc_idx > after_idx:
                return sc
        return None

    async def _publish_community_cards() -> None:
        broadcast_msg = _build_event_message(
            table, "community_cards", session_id,
            street=table.phase,
            state_patch={
                "phase": table.phase,
                "board": table.board.to_dict(),
                "pot": table.pot,
                "current_action_seat": table.current_action_seat,
                "players": {sid: {"current_bet": p.current_bet}
                            for sid, p in table.players.items()},
            },
        )
        await table_service.publish_event(table_id, broadcast_msg)

    next_street = _next_street(current_idx)
    if next_street is not None and _should_auto_runout(table):
        # No further player decisions are possible; deal all remaining streets now.
        while next_street is not None:
            engine.deal_street(next_street)
            await table_service.save_table(table)
            await _publish_community_cards()
            current_idx = street_order.index(table.phase) if table.phase in street_order else -1
            next_street = _next_street(current_idx)

    active = [p for p in table.players.values() if p.status in ("active", "all_in")]
    if next_street is None or len([p for p in active if p.status == "active"]) <= 1:
        # Showdown (showdown() already increments action_seq)
        winnings = engine.showdown()

        winners_payload = {sid: amt for sid, amt in winnings.items() if amt > 0}
        broadcast_msg = _build_event_message(
            table, "hand_complete", session_id,
            winners=winners_payload,
            state_patch={
                "phase": table.phase,
                "pot": table.pot,
                "side_pots": [sp.to_dict() for sp in table.side_pots],
                "players": _build_public_hand_complete_players(table),
                "hand_log": [entry.to_dict() for entry in table.hand_log],
            },
        )
        await table_service.save_table(table)
        await table_service.publish_event(table_id, broadcast_msg)

        # End hand after a short delay to allow clients to display showdown
        await asyncio.sleep(3)

        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)
            variant2 = ShortdeckVariant() if table.rules.variant == "shortdeck" else HoldemVariant()
            engine2 = GameEngine(table, table.rules, variant2)
            engine2.end_hand()
            # end_hand() already increments action_seq
            await table_service.save_table(table)

            end_msg = _build_event_message(
                table, "hand_ended", session_id,
                state_patch={
                    "phase": table.phase,
                    "dealer_seat": table.dealer_seat,
                    "players": {sid: {"stack": p.stack, "status": p.status, "current_bet": p.current_bet}
                                for sid, p in table.players.items()},
                },
            )
            await table_service.publish_event(table_id, end_msg)
    else:
        # Deal next street (deal_street already increments action_seq)
        engine.deal_street(next_street)

        # First to act post-flop: first active player left of dealer
        active_sorted = sorted(
            [p for p in table.players.values() if p.status == "active"],
            key=lambda p: p.seat,
        )
        after_dealer = [p for p in active_sorted if p.seat > table.dealer_seat]
        first_to_act = (after_dealer[0] if after_dealer else active_sorted[0]) if active_sorted else None
        if first_to_act:
            table.current_action_seat = first_to_act.seat

        await table_service.save_table(table)
        await _publish_community_cards()
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

            if session_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error", "code": "NOT_SEATED",
                    "message": "Only seated players can vote",
                })
                return

            if vote == "for":
                table.pending_vote.votes_for.add(session_id)
                table.pending_vote.votes_against.discard(session_id)
            else:
                table.pending_vote.votes_against.add(session_id)
                table.pending_vote.votes_for.discard(session_id)

            table.action_seq += 1

            # Check for majority
            seated_count = len([p for p in table.players.values() if p.status not in ("sitting_out", "disconnected")])
            majority = seated_count // 2 + 1

            if len(table.pending_vote.votes_for) >= majority or len(table.pending_vote.votes_against) >= majority:
                passed = len(table.pending_vote.votes_for) >= majority
                if passed:
                    table.rules = table.pending_vote.proposed_rules
                # Clear all vote/pause state atomically
                table.is_paused = False
                table.pause_requested_by = None
                table.pending_vote = None
                await table_service.save_table(table)

                vote_resolved_msg = _build_event_message(
                    table, "vote_resolved", session_id,
                    passed=passed,
                    new_rules=table.rules.to_dict() if passed else None,
                )
                await table_service.append_event(table_id, vote_resolved_msg)
                await table_service.publish_event(table_id, vote_resolved_msg)
            else:
                await table_service.save_table(table)

                vote_update_msg = _build_event_message(
                    table, "vote_update", session_id,
                    votes_for=len(table.pending_vote.votes_for),
                    votes_against=len(table.pending_vote.votes_against),
                    total_eligible=seated_count,
                    pending_vote=table.pending_vote.to_dict(),
                )
                await table_service.append_event(table_id, vote_update_msg)
                await table_service.publish_event(table_id, vote_update_msg)

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
                if ev.get("seq", 0) >= from_seq:
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

            # Spectator disconnect: just remove from spectators list
            if session_id not in table.players:
                if session_id in table.spectators:
                    table.spectators.remove(session_id)
                    table.action_seq += 1
                    await table_service.save_table(table)
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

            # Build player patch: update disconnected player's status + any new admin
            players_patch = {
                session_id: {"status": "disconnected"},
            }
            if table.admin_id != session_id:
                # Admin transferred — update new admin's is_admin flag in the patch
                players_patch[table.admin_id] = {"is_admin": True}

            broadcast_msg = _build_event_message(
                table, "player_disconnected", session_id,
                admin_id=table.admin_id,
                players=players_patch,
            )
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


async def _handle_propose_rule_change(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Handle a rule change proposal — any player can propose, starts a vote."""
    try:
        from ..models.schemas import TableRulesSchema
        _schema = TableRulesSchema(**msg["proposed_rules"])
        proposed_rules = TableRules.from_dict(_schema.model_dump())
    except (KeyError, Exception) as exc:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "INVALID_RULES",
            "message": f"Invalid proposed rules: {exc}",
        })
        return

    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if session_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error", "code": "NOT_SEATED",
                    "message": "Only seated players can propose rule changes",
                })
                return

            if table.pending_vote is not None:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "VOTE_ALREADY_ACTIVE",
                    "message": "A vote is already in progress",
                })
                return

            seated_player_count = len(table.players)
            if seated_player_count > proposed_rules.compute_max_players():
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "TOO_MANY_PLAYERS",
                    "message": (
                        f"Cannot switch to this game mode: {seated_player_count} players are seated "
                        f"but it only supports up to {proposed_rules.compute_max_players()}."
                    ),
                })
                return

            vote = ModeVote(
                proposed_rules=proposed_rules,
                proposed_by=session_id,
                votes_for={session_id},
                votes_against=set(),
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            table.pending_vote = vote
            table.is_paused = True
            table.pause_requested_by = session_id
            table.action_seq += 1

            await table_service.save_table(table)

            seated_count = len([p for p in table.players.values() if p.status not in ("sitting_out", "disconnected")])
            paused_msg = _build_event_message(
                table, "game_paused", session_id,
                requested_by=session_id,
                pending_vote=vote.to_dict(),
                votes_for=len(vote.votes_for),
                votes_against=len(vote.votes_against),
                total_eligible=seated_count,
            )
            await table_service.append_event(table_id, paused_msg)
            await table_service.publish_event(table_id, paused_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_force_rule_change(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Admin force-applies a rule change without voting."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if table.admin_id != session_id:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_ADMIN",
                    "message": "Only the admin can force rule changes",
                })
                return

            try:
                from ..models.schemas import TableRulesSchema
                _schema = TableRulesSchema(**msg["proposed_rules"])
                new_rules = TableRules.from_dict(_schema.model_dump())
            except (KeyError, Exception) as exc:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "INVALID_RULES",
                    "message": f"Invalid proposed rules: {exc}",
                })
                return

            seated_player_count = len(table.players)
            if seated_player_count > new_rules.compute_max_players():
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "TOO_MANY_PLAYERS",
                    "message": (
                        f"Cannot switch to this game mode: {seated_player_count} players are seated "
                        f"but it only supports up to {new_rules.compute_max_players()}."
                    ),
                })
                return

            table.rules = new_rules
            table.pending_vote = None
            table.is_paused = False
            table.pause_requested_by = None
            table.action_seq += 1

            await table_service.save_table(table)

            resolved_msg = _build_event_message(
                table, "vote_resolved", session_id,
                passed=True,
                new_rules=new_rules.to_dict(),
            )
            await table_service.append_event(table_id, resolved_msg)
            await table_service.publish_event(table_id, resolved_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_pause_request(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Handle a pause request from any player."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if session_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error", "code": "NOT_SEATED",
                    "message": "Only seated players can request a pause",
                })
                return

            table.is_paused = True
            table.pause_requested_by = session_id
            table.action_seq += 1

            await table_service.save_table(table)

            broadcast_msg = _build_event_message(
                table, "game_paused", session_id,
                requested_by=session_id,
            )
            await table_service.publish_event(table_id, broadcast_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_unpause_request(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Handle an unpause request."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if session_id not in table.players and table.admin_id != session_id:
                await manager.send_personal(table_id, session_id, {
                    "type": "error", "code": "NOT_SEATED",
                    "message": "Only seated players or the admin can unpause",
                })
                return
            if table.pending_vote is not None:
                await manager.send_personal(table_id, session_id, {
                    "type": "error", "code": "VOTE_IN_PROGRESS",
                    "message": "Cannot unpause while a vote is in progress",
                })
                return

            table.is_paused = False
            table.pause_requested_by = None
            table.action_seq += 1

            await table_service.save_table(table)

            broadcast_msg = _build_event_message(
                table, "game_unpaused", session_id,
            )
            await table_service.publish_event(table_id, broadcast_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_reveal_card(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Handle a player revealing one of their hole cards."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            try:
                card_index = int(msg.get("card_index", 0))
            except (TypeError, ValueError):
                await manager.send_personal(table_id, session_id, {
                    "type": "error", "code": "INVALID_CARD_INDEX",
                    "message": "card_index must be an integer",
                })
                return
            if card_index < 0:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "INVALID_CARD_INDEX",
                    "message": "card_index must be a non-negative integer",
                })
                return

            if session_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_AT_TABLE",
                    "message": "You are not seated at this table",
                })
                return

            player = table.players[session_id]

            if not player.hole_cards or card_index >= len(player.hole_cards):
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NO_CARD",
                    "message": "No card at that index",
                })
                return

            player.is_revealed[card_index] = True
            card = player.hole_cards[card_index]
            table.action_seq += 1

            await table_service.save_table(table)

            broadcast_msg = _build_event_message(
                table, "card_revealed", session_id,
                card_index=card_index,
                card=card.to_dict(),
            )
            await table_service.publish_event(table_id, broadcast_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_rabbit_hunt_request(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Handle a rabbit hunt request — show remaining community cards privately."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if table.phase not in ("showdown", "between_hands"):
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "INVALID_PHASE",
                    "message": "Rabbit hunt only available at showdown or between hands",
                })
                return

            if session_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_AT_TABLE",
                    "message": "You are not seated at this table",
                })
                return

            primary_count = len(table.board.primary)
            remaining_needed = 5 - primary_count

            if remaining_needed <= 0:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NO_RABBIT_AVAILABLE",
                    "message": "All community cards already dealt",
                })
                return

            ghost_deck = copy.deepcopy(table.deck)
            ghost_cards = ghost_deck.deal(remaining_needed)
            # No save — ghost cards are view-only, deck state unchanged

            # Send private message to requester only
            rabbit_msg = {
                "type": "rabbit_hunt",
                "seq": table.action_seq,
                "hand": table.hand_number,
                "cards": [c.to_dict() for c in ghost_cards],
            }
            await manager.send_personal(table_id, session_id, rabbit_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_sit_down_request(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Handle a spectator requesting to sit down at the table."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            try:
                seat = int(msg["seat"])
                chips = int(msg["chips"])
            except (KeyError, TypeError, ValueError):
                await manager.send_personal(table_id, session_id, {
                    "type": "error", "code": "INVALID_PAYLOAD",
                    "message": "seat and chips must be integers",
                })
                return

            if session_id in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "ALREADY_SEATED",
                    "message": "You are already seated at this table",
                })
                return

            taken_seats = {p.seat for p in table.players.values()}
            if seat in taken_seats:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "SEAT_TAKEN",
                    "message": "That seat is already occupied",
                })
                return

            if not (0 <= seat < table.rules.max_players):
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "INVALID_SEAT",
                    "message": "Seat number out of range",
                })
                return

            if chips <= 0:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "INVALID_CHIPS",
                    "message": "Chips must be greater than zero",
                })
                return

            # Check not already in pending requests
            if any(r["session_id"] == session_id for r in table.pending_sit_requests):
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "REQUEST_ALREADY_PENDING",
                    "message": "You already have a pending sit-down request",
                })
                return

            if len(table.pending_sit_requests) >= 20:
                await manager.send_personal(table_id, session_id, {
                    "type": "error", "code": "TOO_MANY_REQUESTS",
                    "message": "Too many pending sit-down requests",
                })
                return

            session_service = SessionService()
            try:
                requester = await session_service.get_session(session_id)
                requester_name = requester.name
            except Exception:
                requester_name = session_id  # fallback

            table.pending_sit_requests.append({
                "session_id": session_id,
                "seat": seat,
                "chips": chips,
                "name": requester_name,
            })
            table.action_seq += 1

            await table_service.save_table(table)

            print(f"[SIT_DOWN_REQUEST] requester={session_id} name={requester_name} seat={seat} chips={chips}")
            print(f"[SIT_DOWN_REQUEST] table.admin_id={table.admin_id}")
            print(f"[SIT_DOWN_REQUEST] admin connected={manager.is_connected(table_id, table.admin_id)}")
            print(f"[SIT_DOWN_REQUEST] all connected sessions={manager.get_connected_sessions(table_id)}")
            print(f"[SIT_DOWN_REQUEST] pending_sit_requests now={table.pending_sit_requests}")

            broadcast_msg = _build_event_message(
                table, "sit_down_request", session_id,
                seat=seat,
                chips=chips,
            )
            await table_service.publish_event(table_id, broadcast_msg)

            # Send admin a personal message with the full pending list
            await manager.send_personal(table_id, table.admin_id, {
                "type": "sit_down_request",
                "session_id": session_id,
                "seat": seat,
                "chips": chips,
                "name": requester_name,
                "pending_sit_requests": table.pending_sit_requests,
            })
            print(f"[SIT_DOWN_REQUEST] personal message sent to admin {table.admin_id}")

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_approve_sit_down(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Admin approves a sit-down request."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if table.admin_id != session_id:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_ADMIN",
                    "message": "Only the admin can approve sit-down requests",
                })
                return

            target_id = msg.get("session_id")
            request = None
            for r in table.pending_sit_requests:
                if r["session_id"] == target_id:
                    request = r
                    break

            if request is None:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "REQUEST_NOT_FOUND",
                    "message": "No pending sit-down request found for that player",
                })
                return

            table.pending_sit_requests.remove(request)

            seat = request["seat"]
            chips = request["chips"]
            status = "sitting_out" if table.phase not in ("waiting", "between_hands") else "active"

            new_player = Player(
                session_id=target_id,
                name=request.get("name", target_id),
                stack=chips,
                hole_cards=[],
                seat=seat,
                status=status,
                is_admin=False,
            )
            table.players[target_id] = new_player

            if target_id not in table.player_join_order:
                table.player_join_order.append(target_id)

            if target_id in table.spectators:
                table.spectators.remove(target_id)

            table.action_seq += 1

            await table_service.save_table(table)

            # Build a public player dict (no hole cards)
            player_dict = new_player.to_dict()
            player_dict["hole_cards"] = []

            broadcast_msg = _build_event_message(
                table, "sit_down_approved", target_id,
                seat=seat,
                chips=chips,
                players={target_id: player_dict},
                player_join_order=table.player_join_order,
                spectators=table.spectators,
                pending_sit_requests=[],
            )
            await table_service.publish_event(table_id, broadcast_msg)

            # Send admin a personal message with updated pending_sit_requests
            await manager.send_personal(table_id, table.admin_id, {
                "type": "sit_down_approved",
                "session_id": target_id,
                "seat": seat,
                "chips": chips,
                "pending_sit_requests": table.pending_sit_requests,
            })

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_reject_sit_down(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Admin rejects a sit-down request."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if table.admin_id != session_id:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_ADMIN",
                    "message": "Only the admin can reject sit-down requests",
                })
                return

            target_id = msg.get("session_id")

            # Remove matching request if found
            table.pending_sit_requests = [
                r for r in table.pending_sit_requests if r["session_id"] != target_id
            ]

            table.action_seq += 1

            await table_service.save_table(table)

            # Send personal rejection to the target
            await manager.send_personal(table_id, target_id, {
                "type": "sit_down_rejected",
                "session_id": target_id,
            })

            # Broadcast to all
            broadcast_msg = _build_event_message(
                table, "sit_down_rejected", session_id,
                rejected_session_id=target_id,
            )
            await table_service.publish_event(table_id, broadcast_msg)

            # Send admin a personal message with updated pending_sit_requests
            await manager.send_personal(table_id, table.admin_id, {
                "type": "sit_down_rejected",
                "session_id": target_id,
                "pending_sit_requests": table.pending_sit_requests,
            })

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_stand_up(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Handle a player voluntarily standing up from the table."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if session_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_AT_TABLE",
                    "message": "You are not seated at this table",
                })
                return

            player = table.players[session_id]
            if player.status != "sitting_out":
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "MUST_SIT_OUT_FIRST",
                    "message": "You must sit out before standing up",
                })
                return

            del table.players[session_id]
            if session_id in table.player_join_order:
                table.player_join_order.remove(session_id)

            if session_id not in table.spectators:
                table.spectators.append(session_id)

            table.action_seq += 1

            await table_service.save_table(table)

            broadcast_msg = _build_event_message(
                table, "player_stood_up", session_id,
                removed_players=[session_id],
                player_join_order=table.player_join_order,
                spectators=table.spectators,
            )
            await table_service.publish_event(table_id, broadcast_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_sit_out(
    table_id: str,
    session_id: str,
    table_service: TableService,
) -> None:
    """Mark a seated player as sitting_out so they are skipped next hand."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if session_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_AT_TABLE",
                    "message": "You are not seated at this table",
                })
                return

            player = table.players[session_id]
            if player.status == "sitting_out":
                return  # already sitting out

            # Don't allow sit_out if currently in an active hand (folding out mid-hand is not sit-out)
            if player.status in ("active", "all_in") and table.phase not in ("waiting", "between_hands"):
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "CANNOT_SIT_OUT_MID_HAND",
                    "message": "Cannot sit out during an active hand",
                })
                return

            player.status = "sitting_out"
            table.action_seq += 1
            await table_service.save_table(table)

            broadcast_msg = _build_event_message(
                table, "player_sit_out", session_id,
                players={session_id: {"status": "sitting_out"}},
            )
            await table_service.publish_event(table_id, broadcast_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_sit_in(
    table_id: str,
    session_id: str,
    table_service: TableService,
) -> None:
    """Return a sitting_out player to active so they are dealt in next hand."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if session_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_AT_TABLE",
                    "message": "You are not seated at this table",
                })
                return

            player = table.players[session_id]
            if player.status != "sitting_out":
                return  # already active

            player.status = "active"
            table.action_seq += 1
            await table_service.save_table(table)

            broadcast_msg = _build_event_message(
                table, "player_sit_in", session_id,
                players={session_id: {"status": "active"}},
            )
            await table_service.publish_event(table_id, broadcast_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_host_stand_up(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Admin forces a player to stand up."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if table.admin_id != session_id:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_ADMIN",
                    "message": "Only the admin can force players to stand",
                })
                return

            target_id = msg.get("session_id")

            if target_id not in table.players:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_AT_TABLE",
                    "message": "Target player is not seated at this table",
                })
                return

            if table.phase not in ("waiting", "between_hands"):
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "CANNOT_STAND_MID_HAND",
                    "message": "Cannot stand up a player during an active hand",
                })
                return

            del table.players[target_id]
            if target_id in table.player_join_order:
                table.player_join_order.remove(target_id)

            if target_id not in table.spectators:
                table.spectators.append(target_id)

            table.action_seq += 1

            await table_service.save_table(table)

            broadcast_msg = _build_event_message(
                table, "player_stood_up", session_id,
                target_session_id=target_id,
                removed_players=[target_id],
                player_join_order=table.player_join_order,
                spectators=table.spectators,
            )
            await table_service.publish_event(table_id, broadcast_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_host_remove_player(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Admin removes a player entirely from the table."""
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if table.admin_id != session_id:
                await manager.send_personal(table_id, session_id, {
                    "type": "error",
                    "code": "NOT_ADMIN",
                    "message": "Only the admin can remove players",
                })
                return

            target_id = msg.get("session_id")

            # Remove from players if present
            table.players.pop(target_id, None)

            # Remove from spectators if present
            if target_id in table.spectators:
                table.spectators.remove(target_id)

            # Remove from join order if present
            if target_id in table.player_join_order:
                table.player_join_order.remove(target_id)

            # Remove from pending sit requests if present
            table.pending_sit_requests = [
                r for r in table.pending_sit_requests if r["session_id"] != target_id
            ]

            table.action_seq += 1

            await table_service.save_table(table)

            broadcast_msg = _build_event_message(
                table, "player_removed", session_id,
                target_session_id=target_id,
                removed_players=[target_id],
                player_join_order=table.player_join_order,
                spectators=table.spectators,
            )
            await table_service.publish_event(table_id, broadcast_msg)

    except HTTPException:
        await manager.send_personal(table_id, session_id, {
            "type": "error",
            "code": "LOCK_CONFLICT",
            "message": "Action in progress, please retry",
        })


async def _handle_chat_message(
    table_id: str,
    session_id: str,
    msg: dict,
    table_service: TableService,
) -> None:
    """Broadcast a chat message to all players at the table."""
    text = str(msg.get("text", "")).strip()
    if not text:
        return
    # Truncate to prevent abuse
    text = text[:300]

    # Resolve sender name: prefer seated player name, fall back to session name
    try:
        table = await table_service.get_table(table_id)
        if session_id in table.players:
            sender_name = table.players[session_id].name
        else:
            session_service = SessionService()
            session = await session_service.get_session(session_id)
            sender_name = session.name
    except Exception:
        sender_name = "Unknown"

    timestamp = datetime.utcnow().isoformat() + "Z"
    await table_service.publish_event(table_id, {
        "type": "chat_message",
        "session_id": session_id,
        "sender": sender_name,
        "text": text,
        "timestamp": timestamp,
    })
