
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
    extra_flop: bool = False
    street_modifiers: dict[str, int] = Field(default_factory=dict)
    max_players: int = Field(default=9, ge=2)
    allow_rebuy: bool = True

    @model_validator(mode="after")
    def _validate_max_players(self) -> "TableRulesSchema":
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
