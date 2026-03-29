
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from .card import Card
@dataclass
class Player:
    session_id: str
    name: str
    stack: int
    hole_cards: list[Card]
    seat: int
    status: Literal["active", "folded", "all_in", "sitting_out", "disconnected"] = "active"
    current_bet: int = 0
    total_in: int = 0  # total chips put in this hand (for side pot calc)
    is_admin: bool = False
    joined_at: datetime = field(default_factory=datetime.utcnow)
    disconnect_at: datetime | None = None
    is_revealed: list[bool] = field(default_factory=lambda: [False, False])
    buy_in: int = 0  # total chips bought in across all buyins/rebuys at this seat

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "stack": self.stack,
            "hole_cards": [c.to_dict() for c in self.hole_cards],
            "seat": self.seat,
            "status": self.status,
            "current_bet": self.current_bet,
            "total_in": self.total_in,
            "is_admin": self.is_admin,
            "joined_at": self.joined_at.isoformat(),
            "disconnect_at": self.disconnect_at.isoformat() if self.disconnect_at else None,
            "is_revealed": self.is_revealed,
            "buy_in": self.buy_in,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        from .card import Card
        return cls(
            session_id=data["session_id"],
            name=data["name"],
            stack=data["stack"],
            hole_cards=[Card.from_dict(c) for c in data.get("hole_cards", [])],
            seat=data["seat"],
            status=data.get("status", "active"),
            current_bet=data.get("current_bet", 0),
            total_in=data.get("total_in", 0),
            is_admin=data.get("is_admin", False),
            joined_at=datetime.fromisoformat(data["joined_at"]) if "joined_at" in data else datetime.utcnow(),
            disconnect_at=datetime.fromisoformat(data["disconnect_at"]) if data.get("disconnect_at") else None,
            is_revealed=data.get("is_revealed", [False, False]),
            buy_in=data.get("buy_in", 0),
        )
