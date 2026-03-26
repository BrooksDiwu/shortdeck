from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .table import Table
    from .player import Player


@dataclass
class SidePot:
    amount: int
    eligible_players: set[str]  # session_ids

    def to_dict(self) -> dict:
        return {
            "amount": self.amount,
            "eligible_players": list(self.eligible_players),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SidePot":
        return cls(
            amount=data["amount"],
            eligible_players=set(data["eligible_players"]),
        )


class BettingEngine:
    """Handles all chip movement, pot construction, and action validation."""

    @staticmethod
    def validate_action(table: "Table", session_id: str, action: str, amount: int = 0) -> None:
        """Raise ValueError if action is invalid."""
        player = table.players[session_id]
        active_players = [p for p in table.players.values() if p.status in ("active", "all_in")]
        max_current_bet = max(p.current_bet for p in active_players) if active_players else 0

        if action == "fold":
            pass  # always valid
        elif action == "check":
            if player.current_bet < max_current_bet:
                raise ValueError("Cannot check when there is a bet to call")
        elif action == "call":
            call_amount = max_current_bet - player.current_bet
            if call_amount <= 0:
                raise ValueError("Nothing to call")
        elif action == "raise":
            call_amount = max_current_bet - player.current_bet
            min_raise = table.rules.big_blind  # simplified: use bb as min raise floor
            if amount < call_amount + min_raise:
                raise ValueError(f"Raise must be at least {call_amount + min_raise}")
            if table.rules.betting == "pot_limit":
                pot_max = table.pot + 2 * call_amount
                if amount > pot_max:
                    raise ValueError(f"Pot-limit max raise is {pot_max}")
        elif action == "all_in":
            pass  # always valid
        else:
            raise ValueError(f"Unknown action: {action}")

    @staticmethod
    def apply_action(table: "Table", session_id: str, action: str, amount: int = 0) -> None:
        """Apply action to table state. Mutates table in place."""
        player = table.players[session_id]
        active_players = [p for p in table.players.values() if p.status in ("active", "all_in")]
        max_current_bet = max(p.current_bet for p in active_players) if active_players else 0

        if action == "fold":
            player.status = "folded"
        elif action == "check":
            pass
        elif action == "call":
            call_amount = min(max_current_bet - player.current_bet, player.stack)
            player.stack -= call_amount
            player.current_bet += call_amount
            player.total_in += call_amount
            table.pot += call_amount
            if player.stack == 0:
                player.status = "all_in"
        elif action == "raise":
            total_to_pay = amount - player.current_bet
            actual_pay = min(total_to_pay, player.stack)
            player.stack -= actual_pay
            player.current_bet += actual_pay
            player.total_in += actual_pay
            table.pot += actual_pay
            if player.stack == 0:
                player.status = "all_in"
        elif action == "all_in":
            all_in_amount = player.stack
            player.current_bet += all_in_amount
            player.total_in += all_in_amount
            table.pot += all_in_amount
            player.stack = 0
            player.status = "all_in"

    @staticmethod
    def build_side_pots(table: "Table") -> list[SidePot]:
        """
        Build side pots from player total contributions.
        Algorithm from README Section 5.
        """
        contributions = [
            (sid, p.total_in)
            for sid, p in table.players.items()
            if p.total_in > 0
        ]
        contributions.sort(key=lambda x: x[1])

        side_pots: list[SidePot] = []
        already_allocated = 0

        for i, (sid, cap) in enumerate(contributions):
            pot_amount = sum(min(total, cap) for _, total in contributions) - already_allocated
            if pot_amount <= 0:
                continue
            eligible = {s for s, total in contributions if total >= cap}
            # Only include players who haven't folded
            eligible = {s for s in eligible if table.players[s].status != "folded"}
            side_pots.append(SidePot(amount=pot_amount, eligible_players=eligible))
            already_allocated += pot_amount

        return side_pots

    @staticmethod
    def reset_street_bets(table: "Table") -> None:
        """Reset current_bet for all players at the start of a new street."""
        for player in table.players.values():
            player.current_bet = 0
        table.last_aggressor_seat = None

    @staticmethod
    def post_blinds(table: "Table") -> None:
        """Post small and big blinds. Advances action to player after BB."""
        seated = sorted(
            [p for p in table.players.values() if p.status not in ("sitting_out", "disconnected")],
            key=lambda p: p.seat,
        )
        if len(seated) < 2:
            return

        # Find dealer position, then SB and BB
        dealer_idx = next((i for i, p in enumerate(seated) if p.seat == table.dealer_seat), 0)
        sb_idx = (dealer_idx + 1) % len(seated)
        bb_idx = (dealer_idx + 2) % len(seated)

        sb_player = seated[sb_idx]
        bb_player = seated[bb_idx]
        utg_idx = (dealer_idx + 3) % len(seated)

        # Post SB
        sb_amount = min(table.rules.small_blind, sb_player.stack)
        sb_player.stack -= sb_amount
        sb_player.current_bet = sb_amount
        sb_player.total_in += sb_amount
        table.pot += sb_amount
        if sb_player.stack == 0:
            sb_player.status = "all_in"

        # Post BB
        bb_amount = min(table.rules.big_blind, bb_player.stack)
        bb_player.stack -= bb_amount
        bb_player.current_bet = bb_amount
        bb_player.total_in += bb_amount
        table.pot += bb_amount
        if bb_player.stack == 0:
            bb_player.status = "all_in"

        table.current_action_seat = seated[utg_idx].seat
        table.last_aggressor_seat = bb_player.seat  # BB is the opener; action must return to them
