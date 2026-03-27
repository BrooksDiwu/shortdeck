from dataclasses import dataclass, field
from typing import Literal

_ABSOLUTE_MAX = 9
_DECK_SIZES = {"holdem": 52, "shortdeck": 36}
_BURN_CARDS = 0
_BASE_STREET_CARDS = {"flop": 3, "turn": 1, "river": 1}


@dataclass
class StreetConfig:
    name: str
    base_cards: int
    card_modifier: int = 0


@dataclass
class TableRules:
    variant: Literal["holdem", "shortdeck"]
    betting: Literal["no_limit", "pot_limit"]
    small_blind: int
    big_blind: int
    denomination: Literal["chips", "usd"] = "chips"
    hole_cards_count: int = 2
    extra_hole_card: bool = False
    must_use_exactly_two_hole_cards: bool = False
    extra_flop: bool = False
    street_modifiers: dict[str, int] = field(default_factory=dict)
    max_players: int = 9
    allow_rebuy: bool = True
    timer_enabled: bool = False
    timer_seconds: int = 30

    def to_dict(self) -> dict:
        return {
            "variant": self.variant,
            "betting": self.betting,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "denomination": self.denomination,
            "hole_cards_count": self.hole_cards_count,
            "extra_hole_card": self.extra_hole_card,
            "must_use_exactly_two_hole_cards": self.must_use_exactly_two_hole_cards,
            "extra_flop": self.extra_flop,
            "street_modifiers": self.street_modifiers,
            "max_players": self.max_players,
            "allow_rebuy": self.allow_rebuy,
            "timer_enabled": self.timer_enabled,
            "timer_seconds": self.timer_seconds,
        }

    def compute_max_players(self) -> int:
        deck = _DECK_SIZES[self.variant]
        primary_board_cards = sum(
            max(0, base + self.street_modifiers.get(street, 0))
            for street, base in _BASE_STREET_CARDS.items()
        )
        secondary_flop_cards = (
            max(0, _BASE_STREET_CARDS["flop"] + self.street_modifiers.get("flop", 0))
            if self.extra_flop
            else 0
        )
        community_cards = primary_board_cards + secondary_flop_cards
        hole = self.hole_cards_count + (1 if self.extra_hole_card else 0)
        budget = (deck - _BURN_CARDS - community_cards) // hole
        return min(budget, _ABSOLUTE_MAX)

    @classmethod
    def from_dict(cls, data: dict) -> "TableRules":
        return cls(
            variant=data["variant"],
            betting=data["betting"],
            small_blind=data["small_blind"],
            big_blind=data["big_blind"],
            denomination=data.get("denomination", "chips"),
            hole_cards_count=data.get("hole_cards_count", 2),
            extra_hole_card=data.get("extra_hole_card", False),
            must_use_exactly_two_hole_cards=data.get("must_use_exactly_two_hole_cards", False),
            extra_flop=data.get("extra_flop", False),
            street_modifiers=data.get("street_modifiers", {}),
            max_players=data.get("max_players", 9),
            allow_rebuy=data.get("allow_rebuy", True),
            timer_enabled=data.get("timer_enabled", False),
            timer_seconds=data.get("timer_seconds", 30),
        )
