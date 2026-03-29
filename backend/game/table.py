
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from .card import Card
from .player import Player
from .table_rules import TableRules
from .deck import Deck
from .betting import SidePot
@dataclass
class Board:
    primary: list[Card] = field(default_factory=list)
    secondary: list[Card] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "primary": [c.to_dict() for c in self.primary],
            "secondary": [c.to_dict() for c in self.secondary],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Board":
        return cls(
            primary=[Card.from_dict(c) for c in data.get("primary", [])],
            secondary=[Card.from_dict(c) for c in data.get("secondary", [])],
        )
@dataclass
class ModeVote:
    proposed_rules: TableRules
    proposed_by: str
    votes_for: set[str]
    votes_against: set[str]
    expires_at: datetime

    def to_dict(self) -> dict:
        return {
            "proposed_rules": self.proposed_rules.to_dict(),
            "proposed_by": self.proposed_by,
            "votes_for": list(self.votes_for),
            "votes_against": list(self.votes_against),
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModeVote":
        return cls(
            proposed_rules=TableRules.from_dict(data["proposed_rules"]),
            proposed_by=data["proposed_by"],
            votes_for=set(data["votes_for"]),
            votes_against=set(data["votes_against"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )


@dataclass
class HandLogWinner:
    session_id: str
    name: str
    amount_won: int
    hand_description: str | None = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "amount_won": self.amount_won,
            "hand_description": self.hand_description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HandLogWinner":
        return cls(
            session_id=data["session_id"],
            name=data["name"],
            amount_won=data["amount_won"],
            hand_description=data.get("hand_description"),
        )


@dataclass
class HandLogShownHand:
    session_id: str
    name: str
    seat: int
    hole_cards: list[Card]
    best_hand: str
    amount_won: int = 0

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "seat": self.seat,
            "hole_cards": [c.to_dict() for c in self.hole_cards],
            "best_hand": self.best_hand,
            "amount_won": self.amount_won,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HandLogShownHand":
        return cls(
            session_id=data["session_id"],
            name=data["name"],
            seat=data["seat"],
            hole_cards=[Card.from_dict(c) for c in data.get("hole_cards", [])],
            best_hand=data["best_hand"],
            amount_won=data.get("amount_won", 0),
        )


@dataclass
class HandLogEntry:
    hand_number: int
    completed_at: datetime
    showdown: bool
    pot: int
    board: Board
    winners: list[HandLogWinner] = field(default_factory=list)
    shown_hands: list[HandLogShownHand] = field(default_factory=list)
    action_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "hand_number": self.hand_number,
            "completed_at": self.completed_at.isoformat(),
            "showdown": self.showdown,
            "pot": self.pot,
            "board": self.board.to_dict(),
            "winners": [winner.to_dict() for winner in self.winners],
            "shown_hands": [hand.to_dict() for hand in self.shown_hands],
            "action_lines": self.action_lines,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HandLogEntry":
        return cls(
            hand_number=data["hand_number"],
            completed_at=datetime.fromisoformat(data["completed_at"]),
            showdown=data["showdown"],
            pot=data["pot"],
            board=Board.from_dict(data["board"]),
            winners=[HandLogWinner.from_dict(w) for w in data.get("winners", [])],
            shown_hands=[HandLogShownHand.from_dict(hand) for hand in data.get("shown_hands", [])],
            action_lines=data.get("action_lines", []),
        )


@dataclass
class Table:
    table_id: str
    players: dict[str, Player]
    player_join_order: list[str]
    admin_id: str
    rules: TableRules
    board: Board
    pot: int
    side_pots: list[SidePot]
    deck: Deck
    dealer_seat: int
    current_action_seat: int
    name: str = ""
    phase: Literal["waiting", "preflop", "flop", "turn", "river", "showdown", "between_hands"] = "waiting"
    hand_number: int = 0
    action_seq: int = 0
    pending_vote: ModeVote | None = None
    spectators: list[str] = field(default_factory=list)
    pending_sit_requests: list[dict] = field(default_factory=list)
    is_paused: bool = False
    pause_requested_by: str | None = None
    last_aggressor_seat: int | None = None  # seat of last bet/raise, or opener on check-around streets
    hand_log: list[HandLogEntry] = field(default_factory=list)
    current_hand_actions: list[str] = field(default_factory=list)
    hand_started_at: datetime | None = None
    last_action_at: datetime | None = None
    leaderboard: list[dict] = field(default_factory=list)  # stood-up players: {session_id, name, buy_in, final_stack}
    pending_rebuys: list[dict] = field(default_factory=list)  # {session_id, amount} — applied at next hand start
    showdown_order: list[str] = field(default_factory=list)  # session_ids in reveal/muck order
    showdown_index: int = 0  # pointer into showdown_order for next decision
    showdown_shown: list[str] = field(default_factory=list)  # session_ids that have shown
    showdown_mucked: list[str] = field(default_factory=list)  # session_ids that have mucked
    showdown_top_shown_session_id: str | None = None  # current strongest shown hand

    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "name": self.name,
            "players": {sid: p.to_dict() for sid, p in self.players.items()},
            "player_join_order": self.player_join_order,
            "admin_id": self.admin_id,
            "rules": self.rules.to_dict(),
            "board": self.board.to_dict(),
            "pot": self.pot,
            "side_pots": [sp.to_dict() for sp in self.side_pots],
            "deck": self.deck.to_dict(),
            "dealer_seat": self.dealer_seat,
            "current_action_seat": self.current_action_seat,
            "phase": self.phase,
            "hand_number": self.hand_number,
            "action_seq": self.action_seq,
            "pending_vote": self.pending_vote.to_dict() if self.pending_vote else None,
            "spectators": self.spectators,
            "pending_sit_requests": self.pending_sit_requests,
            "is_paused": self.is_paused,
            "pause_requested_by": self.pause_requested_by,
            "last_aggressor_seat": self.last_aggressor_seat,
            "hand_log": [entry.to_dict() for entry in self.hand_log],
            "current_hand_actions": self.current_hand_actions,
            "hand_started_at": self.hand_started_at.isoformat() if self.hand_started_at else None,
            "last_action_at": self.last_action_at.isoformat() if self.last_action_at else None,
            "leaderboard": self.leaderboard,
            "pending_rebuys": self.pending_rebuys,
            "showdown_order": self.showdown_order,
            "showdown_index": self.showdown_index,
            "showdown_shown": self.showdown_shown,
            "showdown_mucked": self.showdown_mucked,
            "showdown_top_shown_session_id": self.showdown_top_shown_session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Table":
        return cls(
            table_id=data["table_id"],
            name=data.get("name", ""),
            players={sid: Player.from_dict(p) for sid, p in data["players"].items()},
            player_join_order=data["player_join_order"],
            admin_id=data["admin_id"],
            rules=TableRules.from_dict(data["rules"]),
            board=Board.from_dict(data["board"]),
            pot=data["pot"],
            side_pots=[SidePot.from_dict(sp) for sp in data.get("side_pots", [])],
            deck=Deck.from_dict(data["deck"]),
            dealer_seat=data["dealer_seat"],
            current_action_seat=data["current_action_seat"],
            phase=data.get("phase", "waiting"),
            hand_number=data.get("hand_number", 0),
            action_seq=data.get("action_seq", 0),
            pending_vote=ModeVote.from_dict(data["pending_vote"]) if data.get("pending_vote") else None,
            spectators=data.get("spectators", []),
            pending_sit_requests=data.get("pending_sit_requests", []),
            is_paused=data.get("is_paused", False),
            pause_requested_by=data.get("pause_requested_by", None),
            last_aggressor_seat=data.get("last_aggressor_seat", None),
            hand_log=[HandLogEntry.from_dict(entry) for entry in data.get("hand_log", [])],
            current_hand_actions=data.get("current_hand_actions", []),
            hand_started_at=datetime.fromisoformat(data["hand_started_at"]) if data.get("hand_started_at") else None,
            last_action_at=datetime.fromisoformat(data["last_action_at"]) if data.get("last_action_at") else None,
            leaderboard=data.get("leaderboard", []),
            pending_rebuys=data.get("pending_rebuys", []),
            showdown_order=data.get("showdown_order", []),
            showdown_index=data.get("showdown_index", 0),
            showdown_shown=data.get("showdown_shown", []),
            showdown_mucked=data.get("showdown_mucked", []),
            showdown_top_shown_session_id=data.get("showdown_top_shown_session_id"),
        )
