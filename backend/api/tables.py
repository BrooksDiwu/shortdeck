import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from ..models.schemas import TableCreate, TableResponse, RebuyRequest
from ..services.table_service import TableService
from ..services.session_service import SessionService
from ..game.table_rules import TableRules

router = APIRouter(prefix="/tables", tags=["tables"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/sessions", auto_error=False)
async def _require_session(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    service = SessionService()
    try:
        session_id = await service.validate_token(token)
        player = await service.get_session(session_id)
        return player
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        )
@router.post("", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    body: TableCreate,
    player=Depends(_require_session),
) -> TableResponse:
    """Create a new table. Creator becomes admin."""
    table_service = TableService()
    rules = TableRules(
        variant=body.rules.variant,
        betting=body.rules.betting,
        small_blind=body.rules.small_blind,
        big_blind=body.rules.big_blind,
        denomination=body.rules.denomination,
        hole_cards_count=body.rules.hole_cards_count,
        extra_hole_card=body.rules.extra_hole_card,
        must_use_exactly_two_hole_cards=body.rules.must_use_exactly_two_hole_cards,
        extra_board=body.rules.extra_board,
        extra_flop=body.rules.extra_flop,
        street_modifiers=body.rules.street_modifiers,
        max_players=body.rules.max_players,
        allow_rebuy=body.rules.allow_rebuy,
        timer_enabled=body.rules.timer_enabled,
        timer_seconds=body.rules.timer_seconds,
    )
    cap = rules.compute_max_players()
    if rules.max_players > cap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"max_players ({rules.max_players}) exceeds card-budget cap of {cap}",
        )
    import json as _json
    table = await table_service.create_table(rules, creator_id=player.session_id, creator=player, name=body.name)
    asyncio.create_task(table_service.persist_table_if_missing(
        table.table_id, _json.dumps(rules.to_dict())
    ))
    return TableResponse(
        table_id=table.table_id,
        name=table.name,
        rules=body.rules,
        phase=table.phase,
        player_count=len(table.players),
        created_at=None,  # set by DB layer
    )
@router.get("", response_model=list[TableResponse])
async def list_tables() -> list[TableResponse]:
    """List open tables (no auth required)."""
    table_service = TableService()
    tables = await table_service.list_tables()
    return [
        TableResponse(
            table_id=t.table_id,
            name=t.name,
            rules=_rules_to_schema(t.rules),
            phase=t.phase,
            player_count=len(t.players),
            created_at=None,
        )
        for t in tables
    ]
@router.get("/{table_id}", response_model=TableResponse)
async def get_table(table_id: str) -> TableResponse:
    """Get table metadata (no auth required)."""
    table_service = TableService()
    try:
        table = await table_service.get_table(table_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    return TableResponse(
        table_id=table.table_id,
        name=table.name,
        rules=_rules_to_schema(table.rules),
        phase=table.phase,
        player_count=len(table.players),
        created_at=None,
    )
@router.post("/{table_id}/join", status_code=status.HTTP_200_OK)
async def join_table(
    table_id: str,
    player=Depends(_require_session),
) -> dict:
    """Join a table as a spectator. Actual seating goes through sit_down_request -> approve_sit_down."""
    table_service = TableService()
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            # Already seated — nothing to do
            if player.session_id in table.players:
                return {"message": "Already at this table"}

            # Already a spectator — nothing to do
            if player.session_id in table.spectators:
                return {"message": "Already at this table"}

            # Add as spectator only
            if len(table.spectators) < 200:
                table.spectators.append(player.session_id)
                await table_service.save_table(table)

    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    return {"message": "Joined table"}
@router.post("/{table_id}/rebuy", status_code=status.HTTP_200_OK)
async def rebuy(
    table_id: str,
    body: RebuyRequest,
    player=Depends(_require_session),
) -> dict:
    """Submit rebuy request — processed between hands."""
    table_service = TableService()
    try:
        async with table_service.acquire_lock(table_id):
            table = await table_service.get_table(table_id)

            if player.session_id not in table.players:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You are not seated at this table",
                )

            if not table.rules.allow_rebuy:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Rebuys are not allowed at this table",
                )

            if table.phase not in ("waiting", "between_hands"):
                # Queue the rebuy on the table — applied at next hand start
                table.pending_rebuys.append({
                    "session_id": player.session_id,
                    "amount": body.amount,
                })
                table.action_seq += 1
                await table_service.save_table(table)
                asyncio.create_task(table_service.persist_stack_transaction(
                    table_id=table_id,
                    session_id=player.session_id,
                    transaction_type="rebuy",
                    amount=body.amount,
                ))
                return {"message": "Rebuy queued — will be applied before next hand"}

            # Apply immediately if between hands
            seated_player = table.players[player.session_id]
            seated_player.stack += body.amount
            seated_player.buy_in += body.amount
            table.action_seq += 1
            await table_service.save_table(table)
            event = {
                "type": "event",
                "seq": table.action_seq,
                "hand": table.hand_number,
                "event_type": "rebuy_applied",
                "session_id": player.session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "state_patch": {
                    "players": {
                        player.session_id: {
                            "stack": seated_player.stack,
                            "buy_in": seated_player.buy_in,
                            "can_request_rebuy": False,
                        }
                    }
                },
            }
            await table_service.append_event(table_id, event)
            await table_service.publish_event(table_id, event)
            asyncio.create_task(table_service.persist_stack_transaction(
                table_id=table_id,
                session_id=player.session_id,
                transaction_type="rebuy",
                amount=body.amount,
            ))

    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    return {"message": f"Rebuy of {body.amount} applied"}
def _rules_to_schema(rules: TableRules):
    from ..models.schemas import TableRulesSchema
    return TableRulesSchema(
        variant=rules.variant,
        betting=rules.betting,
        small_blind=rules.small_blind,
        big_blind=rules.big_blind,
        denomination=rules.denomination,
        hole_cards_count=rules.hole_cards_count,
        extra_hole_card=rules.extra_hole_card,
        must_use_exactly_two_hole_cards=rules.must_use_exactly_two_hole_cards,
        extra_board=rules.extra_board,
        extra_flop=rules.extra_flop,
        street_modifiers=rules.street_modifiers,
        max_players=rules.max_players,
        allow_rebuy=rules.allow_rebuy,
        timer_enabled=rules.timer_enabled,
        timer_seconds=rules.timer_seconds,
    )
