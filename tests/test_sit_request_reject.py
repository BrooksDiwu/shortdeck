import asyncio

from backend.game.deck import Deck
from backend.game.table import Board, Table
from backend.game.table_rules import TableRules
from backend.websocket import router


class _NoopLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeTableService:
    def __init__(self, table: Table):
        self.table = table
        self.published_events: list[dict] = []
        self.saved_tables: int = 0

    def acquire_lock(self, table_id: str):
        return _NoopLock()

    async def get_table(self, table_id: str) -> Table:
        return self.table

    async def save_table(self, table: Table) -> None:
        self.saved_tables += 1
        self.table = table

    async def publish_event(self, table_id: str, event: dict) -> None:
        self.published_events.append(event)


def _make_table() -> Table:
    rules = TableRules(
        variant="holdem",
        betting="no_limit",
        small_blind=50,
        big_blind=100,
    )
    return Table(
        table_id="t1",
        players={},
        player_join_order=[],
        admin_id="admin",
        rules=rules,
        board=Board(),
        pot=0,
        side_pots=[],
        deck=Deck.build("holdem"),
        dealer_seat=0,
        current_action_seat=0,
        phase="waiting",
        hand_number=0,
        action_seq=10,
        spectators=["spec1"],
        pending_sit_requests=[
            {"session_id": "spec1", "seat": 3, "chips": 1000, "name": "Spec One"}
        ],
    )


def test_reject_sit_down_keeps_socket_flow_and_clears_pending(monkeypatch):
    table = _make_table()
    table_service = _FakeTableService(table)
    personal_msgs: list[tuple[str, dict]] = []

    async def _fake_send_personal(table_id: str, session_id: str, msg: dict) -> None:
        personal_msgs.append((session_id, msg))

    monkeypatch.setattr(router.manager, "send_personal", _fake_send_personal)

    asyncio.run(
        router._handle_reject_sit_down(
            table_id="t1",
            session_id="admin",
            msg={"session_id": "spec1"},
            table_service=table_service,
        )
    )

    assert table.pending_sit_requests == []
    assert table_service.saved_tables == 1
    assert any(sid == "spec1" and msg.get("type") == "sit_down_rejected" for sid, msg in personal_msgs)
    assert any(sid == "admin" and msg.get("type") == "sit_down_rejected" for sid, msg in personal_msgs)
    assert len(table_service.published_events) == 1
    event = table_service.published_events[0]
    assert event["event_type"] == "sit_down_rejected"
    assert event["session_id"] == "admin"
    assert event["rejected_session_id"] == "spec1"
