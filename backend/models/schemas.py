
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator
class SessionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
class SessionResponse(BaseModel):
    session_id: str
    token: str
    expires_at: datetime
class TableRulesSchema(BaseModel):
    variant: Literal["holdem", "shortdeck"]
    betting: Literal["no_limit", "pot_limit"]
    small_blind: int = Field(..., ge=1)
    big_blind: int = Field(..., ge=2)
    denomination: Literal["chips", "usd"] = "chips"
    hole_cards_count: int = 2
    extra_hole_card: bool = False
    must_use_exactly_two_hole_cards: bool = False
    extra_board: bool = False
    # Backward-compat alias for extra_board.
    extra_flop: bool = False
    street_modifiers: dict[str, int] = Field(default_factory=dict)
    max_players: int = Field(default=9, ge=2)
    allow_rebuy: bool = True
    timer_enabled: bool = False
    timer_seconds: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def _validate_rules(self) -> "TableRulesSchema":
        enabled = bool(self.extra_board or self.extra_flop)
        self.extra_board = enabled
        self.extra_flop = enabled

        # Validate street modifier ranges:
        #   flop base=3, allowed range 1–5  → mod in [-2, +2]
        #   turn base=1, allowed range 0–3  → mod in [-1, +2]
        #   river base=1, allowed range 0–3 → mod in [-1, +2]
        limits = {"flop": (-2, 2), "turn": (-1, 2), "river": (-1, 2)}
        for street, mod in self.street_modifiers.items():
            if street not in limits:
                raise ValueError(f"Unknown street modifier key: {street!r}")
            lo, hi = limits[street]
            if not (lo <= mod <= hi):
                raise ValueError(
                    f"street_modifiers[{street!r}] = {mod} out of range [{lo}, {hi}]"
                )

        from backend.game.table_rules import TableRules
        rules = TableRules(**self.model_dump())
        cap = rules.compute_max_players()
        if self.max_players > cap:
            raise ValueError(
                f"max_players ({self.max_players}) exceeds the computed "
                f"card-budget cap of {cap} for this variant/rule combination"
            )
        return self
class TableCreate(BaseModel):
    rules: TableRulesSchema
class TableResponse(BaseModel):
    table_id: str
    rules: TableRulesSchema
    phase: str
    player_count: int
    created_at: datetime | None = None
class JoinTableRequest(BaseModel):
    pass  # auth token is used from Authorization header
class RebuyRequest(BaseModel):
    amount: int = Field(..., ge=1)
class ActionRequest(BaseModel):
    action: Literal["fold", "check", "call", "raise", "all_in"]
    amount: int = 0
class VoteRequest(BaseModel):
    vote: Literal["for", "against"]
