
from datetime import datetime, timezone
from .hand_evaluator import HandEvaluator, HandResult
from .table import Board, HandLogEntry, HandLogShownHand, HandLogWinner, Table
from .table_rules import TableRules, StreetConfig
from .betting import BettingEngine, SidePot
from .variants.base import BaseVariant


HAND_LOG_MAX_ENTRIES = 20


class GameEngine:
    def __init__(self, table: Table, rules: TableRules, variant: BaseVariant):
        self.table = table
        self.rules = rules
        self.variant = variant

    def start_hand(self) -> None:
        """Shuffle fresh deck, deal hole cards, post blinds, increment hand_number."""
        table = self.table

        # Expire any pending vote that wasn't resolved before this hand
        if table.pending_vote and datetime.utcnow() > table.pending_vote.expires_at:
            table.pending_vote = None

        # Build and shuffle fresh deck
        table.deck = self.variant.build_deck()
        table.deck.shuffle()

        # Reset board and pot
        table.board.primary = []
        table.board.secondary = []
        table.pot = 0
        table.side_pots = []
        table.current_hand_actions = []

        # Reset player states for new hand
        active_players = [
            p for p in table.players.values()
            if p.status not in ("sitting_out", "disconnected")
        ]
        for p in active_players:
            p.status = "active"
            p.hole_cards = []
            p.is_revealed = []
            p.current_bet = 0
            p.total_in = 0

        # Deal hole cards
        hole_count = self.rules.hole_cards_count + (1 if self.rules.extra_hole_card else 0)
        for p in active_players:
            p.hole_cards = table.deck.deal(hole_count)
            p.is_revealed = [False] * len(p.hole_cards)

        # Post blinds
        BettingEngine.post_blinds(table)

        table.hand_number += 1
        table.action_seq += 1
        table.phase = "preflop"
        table.current_hand_actions.append(f"Hand #{table.hand_number} started")
        self._append_blind_lines()

    def run_betting_round(self) -> None:
        """Placeholder — actual betting driven by WebSocket actions."""
        # Betting is driven externally via BettingEngine.apply_action calls
        # from the WebSocket router under the distributed table lock.
        pass

    def deal_street(self, street: StreetConfig) -> None:
        """Deal community cards, handling optional secondary board."""
        table = self.table
        n = street.base_cards
        if n <= 0:
            return
        new_cards = table.deck.deal(n)
        table.board.primary.extend(new_cards)

        if self.rules.extra_board and street.name in ("flop", "turn", "river"):
            secondary_cards = table.deck.deal(n)
            table.board.secondary.extend(secondary_cards)

        table.current_hand_actions.append(
            f"*** {street.name.upper()} *** [{self._format_cards(new_cards)}]"
        )
        if self.rules.extra_board and street.name in ("flop", "turn", "river"):
            dealt_secondary = table.board.secondary[-n:] if n > 0 else []
            table.current_hand_actions.append(
                f"*** {street.name.upper()} (Board 2) *** [{self._format_cards(dealt_secondary)}]"
            )

        BettingEngine.reset_street_bets(table)
        table.action_seq += 1
        table.phase = street.name

    def showdown(self) -> dict[str, int]:
        """
        Evaluate hands, build side pots, award chips.
        Returns {session_id: amount_won}.
        """
        table = self.table
        table.phase = "showdown"

        # Build side pots from final contributions
        side_pots = BettingEngine.build_side_pots(table)
        table.side_pots = side_pots

        # Collect eligible players for showdown (not folded)
        showdown_players = {
            sid: p for sid, p in table.players.items()
            if p.status in ("active", "all_in")
        }

        winnings: dict[str, int] = {sid: 0 for sid in table.players}
        pot_amount = table.pot

        # If only one player remains (everyone else folded), award pot without evaluation
        if len(showdown_players) == 1:
            winner_sid = next(iter(showdown_players))
            self._distribute_pot(table.pot, [winner_sid], table, winnings)
            for sid, amount in winnings.items():
                if amount > 0:
                    table.players[sid].stack += amount
            self._append_hand_log_entry(
                pot=pot_amount,
                winnings=winnings,
                showdown=False,
                primary_results={},
                secondary_results={},
            )
            table.action_seq += 1
            return winnings

        # Evaluate hands
        player_results: dict[str, HandResult] = {}
        for sid, p in showdown_players.items():
            result = HandEvaluator.evaluate(p.hole_cards, table.board.primary, self.rules)
            player_results[sid] = result

        secondary_results: dict[str, HandResult] = {}

        # If extra board: split pot between two boards
        if self.rules.extra_board and table.board.secondary:
            total = table.pot
            half_primary = total // 2
            half_secondary = total - half_primary  # half_secondary gets the extra chip

            # Board 1 (primary)
            winners_primary = HandEvaluator.find_winners(
                {sid: player_results[sid] for sid in player_results}
            )
            self._distribute_pot(half_primary, winners_primary, table, winnings)

            # Board 2 (secondary)
            for sid, p in showdown_players.items():
                secondary_results[sid] = HandEvaluator.evaluate(
                    p.hole_cards, table.board.secondary, self.rules
                )
            winners_secondary = HandEvaluator.find_winners(secondary_results)
            self._distribute_pot(half_secondary, winners_secondary, table, winnings)
        else:
            # Resolve each side pot independently
            if side_pots:
                for sp in side_pots:
                    eligible_results = {
                        sid: player_results[sid]
                        for sid in sp.eligible_players
                        if sid in player_results
                    }
                    if not eligible_results:
                        # All eligible players folded — give to last remaining active
                        # (edge case: shouldn't normally happen)
                        continue
                    winners = HandEvaluator.find_winners(eligible_results)
                    self._distribute_pot(sp.amount, winners, table, winnings)
            else:
                # No side pots — single pot, open to all non-folded players
                winners = HandEvaluator.find_winners(player_results)
                self._distribute_pot(table.pot, winners, table, winnings)

        # Apply winnings to stacks
        for sid, amount in winnings.items():
            if amount > 0:
                table.players[sid].stack += amount

        self._append_hand_log_entry(
            pot=pot_amount,
            winnings=winnings,
            showdown=True,
            primary_results=player_results,
            secondary_results=secondary_results,
        )
        table.action_seq += 1
        return winnings

    def _distribute_pot(
        self,
        amount: int,
        winners: list[str],
        table: Table,
        winnings: dict[str, int],
    ) -> None:
        """Distribute a pot amount among winners, sending odd chips to first left of dealer."""
        if not winners:
            return
        per_player = amount // len(winners)
        remainder = amount % len(winners)

        for sid in winners:
            winnings[sid] = winnings.get(sid, 0) + per_player

        if remainder > 0:
            # Odd chip(s) go to first winner left of dealer
            seated_winners = sorted(
                [table.players[sid] for sid in winners if sid in table.players],
                key=lambda p: p.seat,
            )
            dealer_seat = table.dealer_seat
            # Find first winner whose seat > dealer_seat, wrapping around
            after_dealer = [p for p in seated_winners if p.seat > dealer_seat]
            if not after_dealer:
                after_dealer = seated_winners  # wrap around
            odd_recipient = after_dealer[0].session_id
            winnings[odd_recipient] = winnings.get(odd_recipient, 0) + remainder

    def _append_hand_log_entry(
        self,
        pot: int,
        winnings: dict[str, int],
        showdown: bool,
        primary_results: dict[str, HandResult],
        secondary_results: dict[str, HandResult],
    ) -> None:
        table = self.table
        hand_descriptions = self._build_hand_descriptions(primary_results, secondary_results)

        shown_hands: list[HandLogShownHand] = []
        if showdown:
            shown_hands = [
                HandLogShownHand(
                    session_id=sid,
                    name=table.players[sid].name,
                    seat=table.players[sid].seat,
                    hole_cards=list(table.players[sid].hole_cards),
                    best_hand=hand_descriptions[sid],
                    amount_won=winnings.get(sid, 0),
                )
                for sid in self._sorted_session_ids(primary_results.keys())
            ]

        winners = [
            HandLogWinner(
                session_id=sid,
                name=table.players[sid].name,
                amount_won=amount,
                hand_description=hand_descriptions.get(sid),
            )
            for sid, amount in sorted(
                ((sid, amount) for sid, amount in winnings.items() if amount > 0),
                key=lambda item: table.players[item[0]].seat,
            )
        ]

        entry = HandLogEntry(
            hand_number=table.hand_number,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            showdown=showdown,
            pot=pot,
            board=Board(
                primary=list(table.board.primary),
                secondary=list(table.board.secondary),
            ),
            winners=winners,
            shown_hands=shown_hands,
            action_lines=self._build_action_lines(showdown, shown_hands, winners),
        )
        table.hand_log = [entry] + table.hand_log[: HAND_LOG_MAX_ENTRIES - 1]

    def _build_hand_descriptions(
        self,
        primary_results: dict[str, HandResult],
        secondary_results: dict[str, HandResult],
    ) -> dict[str, str]:
        descriptions: dict[str, str] = {}
        session_ids = set(primary_results) | set(secondary_results)
        for sid in session_ids:
            primary = primary_results.get(sid)
            secondary = secondary_results.get(sid)
            if primary and secondary:
                descriptions[sid] = (
                    f"Board 1: {self._format_hand_result(primary)} | "
                    f"Board 2: {self._format_hand_result(secondary)}"
                )
            elif primary:
                descriptions[sid] = self._format_hand_result(primary)
            elif secondary:
                descriptions[sid] = self._format_hand_result(secondary)
        return descriptions

    def _format_hand_result(self, result: HandResult) -> str:
        return result.rank.name.replace("_", " ").title()

    def _sorted_session_ids(self, session_ids) -> list[str]:
        return sorted(
            session_ids,
            key=lambda sid: self.table.players[sid].seat,
        )

    def _append_blind_lines(self) -> None:
        table = self.table
        seated = sorted(
            [p for p in table.players.values() if p.status not in ("sitting_out", "disconnected")],
            key=lambda p: p.seat,
        )
        if len(seated) < 2:
            return

        dealer_idx = next((i for i, p in enumerate(seated) if p.seat == table.dealer_seat), 0)
        if len(seated) == 2:
            sb_idx = dealer_idx
            bb_idx = (dealer_idx + 1) % len(seated)
        else:
            sb_idx = (dealer_idx + 1) % len(seated)
            bb_idx = (dealer_idx + 2) % len(seated)

        sb_player = seated[sb_idx]
        bb_player = seated[bb_idx]
        table.current_hand_actions.append(
            f"{sb_player.name}: posts small blind {sb_player.current_bet}"
        )
        table.current_hand_actions.append(
            f"{bb_player.name}: posts big blind {bb_player.current_bet}"
        )

    def _build_action_lines(
        self,
        showdown: bool,
        shown_hands: list[HandLogShownHand],
        winners: list[HandLogWinner],
    ) -> list[str]:
        table = self.table
        lines = list(table.current_hand_actions)

        if showdown:
            lines.append("*** SHOWDOWN ***")
            for shown in shown_hands:
                lines.append(
                    f"{shown.name}: shows [{self._format_cards(shown.hole_cards)}] ({shown.best_hand})"
                )
        else:
            lines.append("*** HAND ENDS BEFORE SHOWDOWN ***")

        for winner in winners:
            if winner.hand_description:
                lines.append(
                    f"{winner.name}: wins {winner.amount_won} with {winner.hand_description}"
                )
            else:
                lines.append(f"{winner.name}: wins {winner.amount_won}")
        return lines

    def _format_cards(self, cards) -> str:
        return " ".join(str(card) for card in cards)

    def end_hand(self) -> None:
        """Rotate dealer, check pending vote, set phase to between_hands."""
        table = self.table

        # Resolve pending vote
        self._resolve_vote()

        # Rotate dealer to next active player
        table.dealer_seat = self._next_dealer_seat()

        # Reset player statuses
        for p in table.players.values():
            if p.status in ("active", "all_in", "folded"):
                # Players who were auto-folded due to disconnect (disconnect_at is set) sit out
                p.status = "sitting_out" if p.disconnect_at is not None else "active"
            p.current_bet = 0
            p.total_in = 0
            p.hole_cards = []
            p.is_revealed = []

        table.pot = 0
        table.side_pots = []
        table.board.primary = []
        table.board.secondary = []
        table.action_seq += 1
        table.phase = "between_hands"

    def build_streets(self) -> list[StreetConfig]:
        streets = self.variant.streets()
        result = []
        for s in streets:
            mod = self.rules.street_modifiers.get(s.name, 0)
            new_cards = s.base_cards + mod
            result.append(StreetConfig(name=s.name, base_cards=new_cards))
        return result

    def _next_dealer_seat(self) -> int:
        """Find next active player seat after current dealer."""
        table = self.table
        active = sorted(
            [p for p in table.players.values() if p.status not in ("sitting_out", "disconnected")],
            key=lambda p: p.seat,
        )
        if not active:
            return table.dealer_seat
        # Find seat strictly after current dealer, wrapping around
        after = [p for p in active if p.seat > table.dealer_seat]
        if after:
            return after[0].seat
        return active[0].seat  # wrap around

    def _resolve_vote(self) -> None:
        """If pending_vote and votes_for > votes_against, swap rules."""
        table = self.table
        vote = table.pending_vote
        if vote is None:
            return
        if len(vote.votes_for) > len(vote.votes_against):
            # Reject if new rules can't seat current players
            seated = len([p for p in table.players.values() if p.status != "left"])
            cap = vote.proposed_rules.compute_max_players()
            if cap < seated:
                table.pending_vote = None
                return
            # Vote passes — swap rules and rebuild variant
            table.rules = vote.proposed_rules
            self.rules = vote.proposed_rules
            # Rebuild variant based on new rules
            if vote.proposed_rules.variant == "shortdeck":
                from .variants.shortdeck import ShortdeckVariant
                self.variant = ShortdeckVariant()
            else:
                from .variants.holdem import HoldemVariant
                self.variant = HoldemVariant()
        table.pending_vote = None
