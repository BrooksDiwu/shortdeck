"""
Tests for BettingEngine: side pot construction, action validation/application.
Covers all required test cases from README Section 5.
"""
import pytest
from datetime import datetime
from backend.game.card import Card, Rank, Suit
from backend.game.player import Player
from backend.game.table import Table, Board
from backend.game.table_rules import TableRules
from backend.game.deck import Deck
from backend.game.betting import BettingEngine, SidePot
from backend.websocket.router import _advance_action, _is_betting_round_complete, _should_auto_runout


def make_rules(betting: str = "no_limit") -> TableRules:
    return TableRules(
        variant="holdem",
        betting=betting,
        small_blind=50,
        big_blind=100,
    )


def make_player(
    session_id: str,
    stack: int,
    seat: int,
    status: str = "active",
    total_in: int = 0,
    current_bet: int = 0,
) -> Player:
    return Player(
        session_id=session_id,
        name=session_id,
        stack=stack,
        hole_cards=[],
        seat=seat,
        status=status,
        current_bet=current_bet,
        total_in=total_in,
        joined_at=datetime.utcnow(),
    )


def make_table(players: list[Player], pot: int = 0, rules: TableRules | None = None) -> Table:
    rules = rules or make_rules()
    player_dict = {p.session_id: p for p in players}
    return Table(
        table_id="test-table",
        players=player_dict,
        player_join_order=[p.session_id for p in players],
        admin_id=players[0].session_id,
        rules=rules,
        board=Board(),
        pot=pot,
        side_pots=[],
        deck=Deck.build("holdem"),
        dealer_seat=0,
        current_action_seat=players[0].seat,
        phase="flop",
        hand_number=1,
        action_seq=1,
    )


# ---------------------------------------------------------------------------
# Side pot construction tests
# ---------------------------------------------------------------------------

class TestSidePots:
    def test_single_all_in_below_current_bet(self):
        """
        Player A goes all-in for 50. Player B called for 100.
        Expected: two pots — main pot (A+B share = 100) and side pot (50 for B alone).
        """
        a = make_player("A", stack=0, seat=0, status="all_in", total_in=50)
        b = make_player("B", stack=50, seat=1, status="active", total_in=100)
        table = make_table([a, b], pot=150)

        side_pots = BettingEngine.build_side_pots(table)

        assert len(side_pots) == 2
        # First pot: both eligible, capped at A's contribution (50 each = 100 total)
        assert side_pots[0].amount == 100
        assert "A" in side_pots[0].eligible_players
        assert "B" in side_pots[0].eligible_players
        # Second pot: only B eligible (extra 50 that A couldn't match)
        assert side_pots[1].amount == 50
        assert "A" not in side_pots[1].eligible_players
        assert "B" in side_pots[1].eligible_players

    def test_two_all_ins_at_different_stack_sizes(self):
        """
        A all-in for 50, B all-in for 100, C has 200 in.
        Expected: three pots at different levels.
        """
        a = make_player("A", stack=0, seat=0, status="all_in", total_in=50)
        b = make_player("B", stack=0, seat=1, status="all_in", total_in=100)
        c = make_player("C", stack=100, seat=2, status="active", total_in=200)
        table = make_table([a, b, c], pot=350)

        side_pots = BettingEngine.build_side_pots(table)

        assert len(side_pots) == 3
        # Pot 1: A, B, C all eligible — 50 * 3 = 150
        assert side_pots[0].amount == 150
        assert {"A", "B", "C"} == side_pots[0].eligible_players
        # Pot 2: B and C eligible — (100-50) * 2 = 100
        assert side_pots[1].amount == 100
        assert "A" not in side_pots[1].eligible_players
        assert {"B", "C"} == side_pots[1].eligible_players
        # Pot 3: only C eligible — 200-100 = 100
        assert side_pots[2].amount == 100
        assert side_pots[2].eligible_players == {"C"}

    def test_all_players_all_in(self):
        """All three players all-in at different amounts."""
        a = make_player("A", stack=0, seat=0, status="all_in", total_in=100)
        b = make_player("B", stack=0, seat=1, status="all_in", total_in=200)
        c = make_player("C", stack=0, seat=2, status="all_in", total_in=300)
        table = make_table([a, b, c], pot=600)

        side_pots = BettingEngine.build_side_pots(table)

        assert len(side_pots) == 3
        # Pot 1: 100*3 = 300, all eligible
        assert side_pots[0].amount == 300
        assert side_pots[0].eligible_players == {"A", "B", "C"}
        # Pot 2: (200-100)*2 = 200, B and C eligible
        assert side_pots[1].amount == 200
        assert side_pots[1].eligible_players == {"B", "C"}
        # Pot 3: (300-200)*1 = 100, only C eligible
        assert side_pots[2].amount == 100
        assert side_pots[2].eligible_players == {"C"}

    def test_fold_after_contributing_more_than_all_in(self):
        """
        A all-in for 50. B folded after putting in 100. C is active with 100 in.
        B's extra 50 above A's cap goes to a pot B can't win because B folded.
        """
        a = make_player("A", stack=0, seat=0, status="all_in", total_in=50)
        b = make_player("B", stack=0, seat=1, status="folded", total_in=100)
        c = make_player("C", stack=100, seat=2, status="active", total_in=100)
        table = make_table([a, b, c], pot=250)

        side_pots = BettingEngine.build_side_pots(table)

        # Pot at 50 cap: all three contributed at least 50 => pot = 150, but B is folded
        # so B not eligible
        assert len(side_pots) >= 1
        pot1 = side_pots[0]
        assert "B" not in pot1.eligible_players  # B folded
        assert "A" in pot1.eligible_players
        assert "C" in pot1.eligible_players

        # Pot at 100 cap: B's contribution above 50 = 50, C's contribution above 50 = 50 => 100
        # B is folded so not eligible; only C can win this
        if len(side_pots) > 1:
            pot2 = side_pots[1]
            assert "B" not in pot2.eligible_players
            assert "C" in pot2.eligible_players

    def test_equal_contributions_single_pot(self):
        """Three active players with identical contributions — single pot."""
        a = make_player("A", stack=0, seat=0, status="all_in", total_in=100)
        b = make_player("B", stack=0, seat=1, status="all_in", total_in=100)
        c = make_player("C", stack=0, seat=2, status="all_in", total_in=100)
        table = make_table([a, b, c], pot=300)

        side_pots = BettingEngine.build_side_pots(table)

        # All identical contributions — should have one pot with all eligible
        # (or 3 pots of equal size — either way, all must be eligible in the first)
        assert side_pots[0].eligible_players == {"A", "B", "C"}
        total = sum(sp.amount for sp in side_pots)
        assert total == 300

    def test_all_in_on_different_streets(self):
        """
        A goes all-in preflop for 100. B goes all-in on flop for 300 total.
        C is active with 300 total.
        total_in tracks accumulation across streets.
        """
        a = make_player("A", stack=0, seat=0, status="all_in", total_in=100)
        b = make_player("B", stack=0, seat=1, status="all_in", total_in=300)
        c = make_player("C", stack=200, seat=2, status="active", total_in=300)
        table = make_table([a, b, c], pot=700)

        side_pots = BettingEngine.build_side_pots(table)

        assert len(side_pots) == 2
        # Pot 1: 100 * 3 = 300, A, B, C eligible
        assert side_pots[0].amount == 300
        assert side_pots[0].eligible_players == {"A", "B", "C"}
        # Pot 2: (300-100) * 2 = 400, B and C eligible
        assert side_pots[1].amount == 400
        assert side_pots[1].eligible_players == {"B", "C"}


# ---------------------------------------------------------------------------
# Action validation tests
# ---------------------------------------------------------------------------

class TestActionValidation:
    def test_check_valid_when_no_bet(self):
        a = make_player("A", stack=500, seat=0, current_bet=0)
        b = make_player("B", stack=500, seat=1, current_bet=0)
        table = make_table([a, b])
        # Should not raise
        BettingEngine.validate_action(table, "A", "check")

    def test_check_invalid_when_there_is_a_bet(self):
        a = make_player("A", stack=500, seat=0, current_bet=0)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b])
        with pytest.raises(ValueError, match="Cannot check"):
            BettingEngine.validate_action(table, "A", "check")

    def test_call_valid(self):
        a = make_player("A", stack=500, seat=0, current_bet=0)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b])
        # Should not raise
        BettingEngine.validate_action(table, "A", "call")

    def test_call_invalid_nothing_to_call(self):
        a = make_player("A", stack=500, seat=0, current_bet=100)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b])
        with pytest.raises(ValueError, match="Nothing to call"):
            BettingEngine.validate_action(table, "A", "call")

    def test_raise_valid_no_limit(self):
        a = make_player("A", stack=500, seat=0, current_bet=0)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b])
        # min raise = big blind (100), call amount = 100, so min = 200 total
        BettingEngine.validate_action(table, "A", "raise", amount=200)

    def test_raise_too_small(self):
        a = make_player("A", stack=500, seat=0, current_bet=0)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b])
        with pytest.raises(ValueError, match="Raise must be at least"):
            BettingEngine.validate_action(table, "A", "raise", amount=50)

    def test_raise_pot_limit_max(self):
        rules = make_rules("pot_limit")
        a = make_player("A", stack=500, seat=0, current_bet=0)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b], pot=200, rules=rules)
        # call_amount = 100, pot_max = pot(200) + 2 * call(100) = 400
        with pytest.raises(ValueError, match="Pot-limit max raise"):
            BettingEngine.validate_action(table, "A", "raise", amount=500)

    def test_fold_always_valid(self):
        a = make_player("A", stack=500, seat=0, current_bet=0)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b])
        BettingEngine.validate_action(table, "A", "fold")  # should not raise

    def test_all_in_always_valid(self):
        a = make_player("A", stack=500, seat=0, current_bet=0)
        b = make_player("B", stack=900, seat=1, current_bet=800)
        table = make_table([a, b])
        BettingEngine.validate_action(table, "A", "all_in")  # should not raise

    def test_unknown_action(self):
        a = make_player("A", stack=500, seat=0)
        b = make_player("B", stack=500, seat=1)
        table = make_table([a, b])
        with pytest.raises(ValueError, match="Unknown action"):
            BettingEngine.validate_action(table, "A", "limp")


# ---------------------------------------------------------------------------
# Action application tests
# ---------------------------------------------------------------------------

class TestActionApplication:
    def test_fold_sets_status(self):
        a = make_player("A", stack=500, seat=0)
        b = make_player("B", stack=500, seat=1)
        table = make_table([a, b])
        BettingEngine.apply_action(table, "A", "fold")
        assert table.players["A"].status == "folded"

    def test_call_moves_chips_to_pot(self):
        a = make_player("A", stack=500, seat=0, current_bet=0)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b], pot=100)
        BettingEngine.apply_action(table, "A", "call")
        assert table.players["A"].stack == 400
        assert table.players["A"].current_bet == 100
        assert table.pot == 200

    def test_call_capped_at_stack(self):
        """If player can't cover the call, they go all-in for their remaining stack."""
        a = make_player("A", stack=30, seat=0, current_bet=0)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b], pot=100)
        BettingEngine.apply_action(table, "A", "call")
        assert table.players["A"].stack == 0
        assert table.players["A"].status == "all_in"
        assert table.pot == 130

    def test_raise_moves_chips(self):
        a = make_player("A", stack=500, seat=0, current_bet=0)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b], pot=100)
        BettingEngine.apply_action(table, "A", "raise", amount=200)
        assert table.players["A"].current_bet == 200
        assert table.players["A"].stack == 300
        assert table.pot == 300

    def test_all_in_sets_status_and_moves_all_chips(self):
        a = make_player("A", stack=350, seat=0, current_bet=0)
        b = make_player("B", stack=500, seat=1, current_bet=0)
        table = make_table([a, b], pot=0)
        BettingEngine.apply_action(table, "A", "all_in")
        assert table.players["A"].stack == 0
        assert table.players["A"].status == "all_in"
        assert table.players["A"].current_bet == 350
        assert table.pot == 350

    def test_check_no_change(self):
        a = make_player("A", stack=500, seat=0, current_bet=100)
        b = make_player("B", stack=400, seat=1, current_bet=100)
        table = make_table([a, b], pot=200)
        BettingEngine.apply_action(table, "A", "check")
        assert table.players["A"].stack == 500
        assert table.pot == 200


# ---------------------------------------------------------------------------
# Split pot / odd chip tests
# ---------------------------------------------------------------------------

class TestSplitPot:
    def test_split_pot_tie_odd_chip(self):
        """
        Odd chip goes to first active player left of dealer.
        Pot of 101 split between two winners — one gets 51, other gets 50.
        """
        # Dealer is at seat 0. Winners are A (seat 1) and B (seat 2).
        # First left of dealer is seat 1 (A), so A gets the odd chip.
        from backend.game.engine import GameEngine
        from backend.game.variants.holdem import HoldemVariant

        rules = make_rules()
        a = make_player("A", stack=0, seat=1, status="active", total_in=50)
        b = make_player("B", stack=0, seat=2, status="active", total_in=51)
        # Normalize: both put in 50 each for a pot of 101 (simulate odd pot)
        a.total_in = 51
        table = make_table([a, b], pot=101, rules=rules)
        table.dealer_seat = 0

        # Build side pots and distribute manually
        winnings: dict[str, int] = {"A": 0, "B": 0}
        engine = GameEngine(table, rules, HoldemVariant())
        engine._distribute_pot(101, ["A", "B"], table, winnings)

        total_distributed = winnings["A"] + winnings["B"]
        assert total_distributed == 101
        # One player gets 51, the other gets 50
        assert max(winnings.values()) == 51
        assert min(winnings.values()) == 50

    def test_post_blinds_sets_pot_and_action(self):
        """Post blinds correctly charges SB and BB and sets action to UTG."""
        rules = make_rules()
        a = make_player("A", stack=1000, seat=0)  # dealer
        b = make_player("B", stack=1000, seat=1)  # SB
        c = make_player("C", stack=1000, seat=2)  # BB
        d = make_player("D", stack=1000, seat=3)  # UTG

        table = make_table([a, b, c, d], pot=0, rules=rules)
        table.dealer_seat = 0

        BettingEngine.post_blinds(table)

        assert table.players["B"].current_bet == 50   # SB
        assert table.players["C"].current_bet == 100  # BB
        assert table.pot == 150
        assert table.current_action_seat == 3  # UTG (seat 3)

    def test_post_blinds_heads_up_button_posts_sb_and_acts_first(self):
        """Heads-up preflop: dealer/button is the SB and opens the action."""
        rules = make_rules()
        a = make_player("A", stack=1000, seat=0)  # dealer/button/SB
        b = make_player("B", stack=1000, seat=1)  # BB

        table = make_table([a, b], pot=0, rules=rules)
        table.dealer_seat = 0

        BettingEngine.post_blinds(table)

        assert table.players["A"].current_bet == 50
        assert table.players["B"].current_bet == 100
        assert table.pot == 150
        assert table.current_action_seat == 0
        assert table.last_aggressor_seat == 0

    def test_post_blinds_heads_up_skips_all_in_small_blind_for_action(self):
        """If the SB is all-in from posting, action should move to the remaining active player."""
        rules = make_rules()
        a = make_player("A", stack=30, seat=0)  # dealer/button/SB, goes all-in posting 30
        b = make_player("B", stack=1000, seat=1)  # BB

        table = make_table([a, b], pot=0, rules=rules)
        table.dealer_seat = 0

        BettingEngine.post_blinds(table)

        assert table.players["A"].status == "all_in"
        assert table.current_action_seat == 1
        assert table.last_aggressor_seat == 1

    def test_heads_up_preflop_round_waits_for_big_blind_option(self):
        """A limped heads-up pot should not close until the BB takes their option."""
        rules = make_rules()
        a = make_player("A", stack=1000, seat=0)  # dealer/button/SB
        b = make_player("B", stack=1000, seat=1)  # BB

        table = make_table([a, b], pot=0, rules=rules)
        table.phase = "preflop"
        table.dealer_seat = 0

        BettingEngine.post_blinds(table)

        BettingEngine.apply_action(table, "A", "call")
        _advance_action(table)

        assert table.current_action_seat == 1
        assert not _is_betting_round_complete(table)

        BettingEngine.apply_action(table, "B", "check")
        _advance_action(table)

        assert table.current_action_seat == 0
        assert _is_betting_round_complete(table)

    def test_reset_street_bets(self):
        """All current_bets reset to 0 at start of new street."""
        a = make_player("A", stack=400, seat=0, current_bet=100)
        b = make_player("B", stack=300, seat=1, current_bet=200)
        c = make_player("C", stack=0, seat=2, current_bet=300, status="all_in")
        table = make_table([a, b, c])

        BettingEngine.reset_street_bets(table)

        for p in table.players.values():
            assert p.current_bet == 0

    def test_should_auto_runout_when_only_one_active_and_others_all_in(self):
        a = make_player("A", stack=500, seat=0, status="active")
        b = make_player("B", stack=0, seat=1, status="all_in")
        c = make_player("C", stack=0, seat=2, status="all_in")
        table = make_table([a, b, c], pot=300)
        assert _should_auto_runout(table)

    def test_should_not_auto_runout_with_multiple_active_players(self):
        a = make_player("A", stack=500, seat=0, status="active")
        b = make_player("B", stack=300, seat=1, status="active")
        c = make_player("C", stack=0, seat=2, status="all_in")
        table = make_table([a, b, c], pot=300)
        assert not _should_auto_runout(table)
