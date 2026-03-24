"""Comprehensive tests for engine.py — GameEngine."""

from datetime import datetime, timedelta

import pytest

from backend.game.betting import SidePot
from backend.game.card import Card, Rank, Suit
from backend.game.deck import Deck
from backend.game.engine import GameEngine
from backend.game.player import Player
from backend.game.table import Board, ModeVote, Table
from backend.game.table_rules import TableRules
from backend.game.variants.holdem import HoldemVariant
from backend.game.variants.shortdeck import ShortdeckVariant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(rank: Rank, suit: Suit) -> Card:
    return Card(rank, suit)


S, H, D, C = Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS
R = Rank


def _make_player(sid: str, seat: int, stack: int = 1000, status: str = "active") -> Player:
    return Player(
        session_id=sid,
        name=sid,
        stack=stack,
        hole_cards=[],
        seat=seat,
        status=status,
        joined_at=datetime(2025, 1, 1),
    )


def _make_table(
    players: dict[str, Player],
    rules: TableRules | None = None,
    dealer_seat: int = 0,
    pot: int = 0,
    phase: str = "waiting",
) -> Table:
    if rules is None:
        rules = TableRules(variant="holdem", betting="no_limit", small_blind=50, big_blind=100)
    return Table(
        table_id="test",
        players=players,
        player_join_order=list(players.keys()),
        admin_id=list(players.keys())[0],
        rules=rules,
        board=Board(),
        pot=pot,
        side_pots=[],
        deck=Deck.build(rules.variant),
        dealer_seat=dealer_seat,
        current_action_seat=0,
        phase=phase,
    )


def _make_engine(
    players: dict[str, Player] | None = None,
    rules: TableRules | None = None,
    dealer_seat: int = 0,
    variant=None,
) -> GameEngine:
    if rules is None:
        rules = TableRules(variant="holdem", betting="no_limit", small_blind=50, big_blind=100)
    if players is None:
        players = {
            "A": _make_player("A", seat=0),
            "B": _make_player("B", seat=1),
            "C": _make_player("C", seat=2),
        }
    table = _make_table(players, rules, dealer_seat=dealer_seat)
    if variant is None:
        variant = HoldemVariant() if rules.variant == "holdem" else ShortdeckVariant()
    return GameEngine(table, rules, variant)


# ===================================================================
# 1. start_hand
# ===================================================================

class TestStartHand:

    def test_deals_correct_hole_cards(self):
        engine = _make_engine()
        engine.start_hand()
        for p in engine.table.players.values():
            assert len(p.hole_cards) == 2

    def test_resets_board(self):
        engine = _make_engine()
        engine.table.board.primary = [_c(R.ACE, S)]
        engine.table.board.secondary = [_c(R.KING, H)]
        engine.start_hand()
        assert engine.table.board.primary == []
        assert engine.table.board.secondary == []

    def test_resets_pot(self):
        engine = _make_engine()
        engine.table.pot = 999
        engine.start_hand()
        # Pot should be blinds only (50 + 100 = 150)
        assert engine.table.pot == 150

    def test_increments_hand_number(self):
        engine = _make_engine()
        assert engine.table.hand_number == 0
        engine.start_hand()
        assert engine.table.hand_number == 1
        engine.start_hand()
        assert engine.table.hand_number == 2

    def test_posts_blinds(self):
        engine = _make_engine()
        engine.start_hand()
        # Blinds are posted; pot should be SB + BB = 150
        assert engine.table.pot == 150

    def test_sets_phase_to_preflop(self):
        engine = _make_engine()
        engine.start_hand()
        assert engine.table.phase == "preflop"

    def test_extra_hole_card(self):
        rules = TableRules(
            variant="holdem", betting="no_limit", small_blind=50, big_blind=100,
            extra_hole_card=True,
        )
        engine = _make_engine(rules=rules)
        engine.start_hand()
        for p in engine.table.players.values():
            assert len(p.hole_cards) == 3  # 2 + 1

    def test_sitting_out_players_not_dealt(self):
        players = {
            "A": _make_player("A", seat=0),
            "B": _make_player("B", seat=1),
            "C": _make_player("C", seat=2, status="sitting_out"),
        }
        engine = _make_engine(players=players)
        engine.start_hand()
        assert len(engine.table.players["A"].hole_cards) == 2
        assert len(engine.table.players["B"].hole_cards) == 2
        assert len(engine.table.players["C"].hole_cards) == 0

    def test_clears_side_pots(self):
        engine = _make_engine()
        engine.table.side_pots = [SidePot(amount=100, eligible_players={"A", "B"})]
        engine.start_hand()
        assert engine.table.side_pots == []

    def test_resets_player_current_bet_and_total_in(self):
        engine = _make_engine()
        for p in engine.table.players.values():
            p.current_bet = 50
            p.total_in = 100
        engine.start_hand()
        # After start_hand, current_bet / total_in are set by post_blinds (not zero for SB/BB)
        # But the reset happens first, then blinds are posted. Non-blind player should have 0.
        # With 3 players (seats 0,1,2), dealer=0, SB=seat1, BB=seat2
        # UTG (seat 0) should have current_bet=0 before action
        # Actually UTG is (dealer+3)%3 = seat 0 in 3-player game
        # SB=seat1, BB=seat2
        sb = engine.table.players["B"]
        bb = engine.table.players["C"]
        assert sb.current_bet == 50  # small blind posted
        assert bb.current_bet == 100  # big blind posted


# ===================================================================
# 2. deal_street
# ===================================================================

class TestDealStreet:

    def test_deal_flop(self):
        from backend.game.table_rules import StreetConfig
        engine = _make_engine()
        engine.start_hand()
        initial_seq = engine.table.action_seq
        engine.deal_street(StreetConfig(name="flop", base_cards=3))
        assert len(engine.table.board.primary) == 3
        assert engine.table.phase == "flop"
        assert engine.table.action_seq == initial_seq + 1

    def test_deal_turn(self):
        from backend.game.table_rules import StreetConfig
        engine = _make_engine()
        engine.start_hand()
        engine.deal_street(StreetConfig(name="flop", base_cards=3))
        engine.deal_street(StreetConfig(name="turn", base_cards=1))
        assert len(engine.table.board.primary) == 4
        assert engine.table.phase == "turn"

    def test_deal_river(self):
        from backend.game.table_rules import StreetConfig
        engine = _make_engine()
        engine.start_hand()
        engine.deal_street(StreetConfig(name="flop", base_cards=3))
        engine.deal_street(StreetConfig(name="turn", base_cards=1))
        engine.deal_street(StreetConfig(name="river", base_cards=1))
        assert len(engine.table.board.primary) == 5
        assert engine.table.phase == "river"

    def test_extra_flop(self):
        from backend.game.table_rules import StreetConfig
        rules = TableRules(
            variant="holdem", betting="no_limit", small_blind=50, big_blind=100,
            extra_flop=True,
        )
        engine = _make_engine(rules=rules)
        engine.start_hand()
        engine.deal_street(StreetConfig(name="flop", base_cards=3))
        assert len(engine.table.board.primary) == 3
        assert len(engine.table.board.secondary) == 3

    def test_extra_flop_only_on_flop_street(self):
        """extra_flop should NOT deal secondary on turn or river."""
        from backend.game.table_rules import StreetConfig
        rules = TableRules(
            variant="holdem", betting="no_limit", small_blind=50, big_blind=100,
            extra_flop=True,
        )
        engine = _make_engine(rules=rules)
        engine.start_hand()
        engine.deal_street(StreetConfig(name="flop", base_cards=3))
        engine.deal_street(StreetConfig(name="turn", base_cards=1))
        # Secondary should still be 3 (from flop), not 4
        assert len(engine.table.board.secondary) == 3
        assert len(engine.table.board.primary) == 4

    def test_deal_zero_cards_noop(self):
        from backend.game.table_rules import StreetConfig
        engine = _make_engine()
        engine.start_hand()
        initial_primary = len(engine.table.board.primary)
        initial_seq = engine.table.action_seq
        engine.deal_street(StreetConfig(name="preflop", base_cards=0))
        assert len(engine.table.board.primary) == initial_primary
        # base_cards <= 0 returns early, so action_seq should NOT increment
        assert engine.table.action_seq == initial_seq


# ===================================================================
# 3. build_streets with street_modifiers
# ===================================================================

class TestBuildStreets:

    def test_default_streets(self):
        engine = _make_engine()
        streets = engine.build_streets()
        names = [s.name for s in streets]
        assert names == ["preflop", "flop", "turn", "river"]
        assert streets[1].base_cards == 3  # flop
        assert streets[2].base_cards == 1  # turn
        assert streets[3].base_cards == 1  # river

    def test_street_modifier_on_turn(self):
        """street_modifiers={'turn': 1} should deal 2 cards on the turn."""
        rules = TableRules(
            variant="holdem", betting="no_limit", small_blind=50, big_blind=100,
            street_modifiers={"turn": 1},
        )
        engine = _make_engine(rules=rules)
        streets = engine.build_streets()
        turn = next(s for s in streets if s.name == "turn")
        assert turn.base_cards == 2  # 1 + 1

    def test_street_modifier_on_flop(self):
        rules = TableRules(
            variant="holdem", betting="no_limit", small_blind=50, big_blind=100,
            street_modifiers={"flop": 2},
        )
        engine = _make_engine(rules=rules)
        streets = engine.build_streets()
        flop = next(s for s in streets if s.name == "flop")
        assert flop.base_cards == 5  # 3 + 2


# ===================================================================
# 4. showdown
# ===================================================================

class TestShowdown:

    def _setup_showdown(self, hole_a, hole_b, community, stacks=None):
        """Helper to set up a table ready for showdown."""
        if stacks is None:
            stacks = {"A": 900, "B": 900}
        players = {
            "A": _make_player("A", seat=0, stack=stacks["A"]),
            "B": _make_player("B", seat=1, stack=stacks["B"]),
        }
        players["A"].hole_cards = hole_a
        players["B"].hole_cards = hole_b
        players["A"].total_in = 100
        players["B"].total_in = 100

        rules = TableRules(variant="holdem", betting="no_limit", small_blind=50, big_blind=100)
        table = _make_table(players, rules, pot=200)
        table.board.primary = community
        table.phase = "river"
        variant = HoldemVariant()
        return GameEngine(table, rules, variant)

    def test_winner_gets_pot(self):
        # A has a flush, B has a pair
        hole_a = [_c(R.ACE, H), _c(R.KING, H)]
        hole_b = [_c(R.TWO, C), _c(R.THREE, D)]
        community = [_c(R.QUEEN, H), _c(R.JACK, H), _c(R.NINE, H), _c(R.FOUR, S), _c(R.FIVE, S)]
        engine = self._setup_showdown(hole_a, hole_b, community)
        winnings = engine.showdown()
        assert winnings["A"] == 200
        assert winnings["B"] == 0

    def test_tie_splits_pot(self):
        # Both play the same board (board has royal flush)
        hole_a = [_c(R.TWO, C), _c(R.THREE, D)]
        hole_b = [_c(R.FOUR, C), _c(R.FIVE, D)]
        community = [_c(R.ACE, S), _c(R.KING, S), _c(R.QUEEN, S), _c(R.JACK, S), _c(R.TEN, S)]
        engine = self._setup_showdown(hole_a, hole_b, community)
        winnings = engine.showdown()
        assert winnings["A"] + winnings["B"] == 200
        # Each gets 100
        assert winnings["A"] == 100
        assert winnings["B"] == 100

    def test_showdown_sets_phase(self):
        hole_a = [_c(R.ACE, H), _c(R.KING, H)]
        hole_b = [_c(R.TWO, C), _c(R.THREE, D)]
        community = [_c(R.QUEEN, H), _c(R.JACK, H), _c(R.NINE, H), _c(R.FOUR, S), _c(R.FIVE, S)]
        engine = self._setup_showdown(hole_a, hole_b, community)
        engine.showdown()
        assert engine.table.phase == "showdown"

    def test_showdown_applies_winnings_to_stack(self):
        hole_a = [_c(R.ACE, H), _c(R.KING, H)]
        hole_b = [_c(R.TWO, C), _c(R.THREE, D)]
        community = [_c(R.QUEEN, H), _c(R.JACK, H), _c(R.NINE, H), _c(R.FOUR, S), _c(R.FIVE, S)]
        engine = self._setup_showdown(hole_a, hole_b, community, stacks={"A": 900, "B": 900})
        engine.showdown()
        assert engine.table.players["A"].stack == 1100  # 900 + 200

    def test_showdown_with_side_pots(self):
        """All-in player can only win their eligible pot."""
        players = {
            "A": _make_player("A", seat=0, stack=0),    # all-in
            "B": _make_player("B", seat=1, stack=500),   # has more chips
        }
        players["A"].status = "all_in"
        players["A"].total_in = 200
        players["B"].total_in = 400
        # A has better hand but can only win 400 (200 * 2 players)
        players["A"].hole_cards = [_c(R.ACE, H), _c(R.KING, H)]
        players["B"].hole_cards = [_c(R.TWO, C), _c(R.THREE, D)]

        rules = TableRules(variant="holdem", betting="no_limit", small_blind=50, big_blind=100)
        table = _make_table(players, rules, pot=600)
        table.board.primary = [_c(R.QUEEN, H), _c(R.JACK, H), _c(R.NINE, H), _c(R.FOUR, S), _c(R.FIVE, S)]
        table.phase = "river"
        engine = GameEngine(table, rules, HoldemVariant())

        winnings = engine.showdown()
        # Side pot 1: min(200,200)+min(200,400)=400, eligible: A and B (A wins with flush)
        # Side pot 2: min(400,200)+min(400,400)-400 = 200+400-400=200, eligible: B only
        # A wins pot 1 (400), B wins pot 2 (200)
        assert winnings["A"] == 400
        assert winnings["B"] == 200

    def test_showdown_folded_player_excluded(self):
        """Folded players should not win at showdown."""
        players = {
            "A": _make_player("A", seat=0, stack=900),
            "B": _make_player("B", seat=1, stack=900),
        }
        players["A"].hole_cards = [_c(R.ACE, H), _c(R.KING, H)]
        players["A"].status = "folded"
        players["B"].hole_cards = [_c(R.TWO, C), _c(R.THREE, D)]
        players["A"].total_in = 100
        players["B"].total_in = 100

        rules = TableRules(variant="holdem", betting="no_limit", small_blind=50, big_blind=100)
        table = _make_table(players, rules, pot=200)
        table.board.primary = [_c(R.QUEEN, H), _c(R.JACK, H), _c(R.NINE, H), _c(R.FOUR, S), _c(R.FIVE, S)]
        table.phase = "river"
        engine = GameEngine(table, rules, HoldemVariant())

        winnings = engine.showdown()
        assert winnings["A"] == 0
        assert winnings["B"] == 200


# ===================================================================
# 5. end_hand
# ===================================================================

class TestEndHand:

    def test_rotates_dealer(self):
        engine = _make_engine(dealer_seat=0)
        engine.table.phase = "showdown"
        engine.end_hand()
        # Dealer should rotate from seat 0 to seat 1
        assert engine.table.dealer_seat == 1

    def test_rotates_dealer_wraps_around(self):
        engine = _make_engine(dealer_seat=2)
        engine.table.phase = "showdown"
        engine.end_hand()
        # Wraps from seat 2 back to seat 0
        assert engine.table.dealer_seat == 0

    def test_resets_pot_and_board(self):
        engine = _make_engine()
        engine.table.pot = 500
        engine.table.board.primary = [_c(R.ACE, S), _c(R.KING, H), _c(R.QUEEN, D)]
        engine.end_hand()
        assert engine.table.pot == 0
        assert engine.table.board.primary == []
        assert engine.table.board.secondary == []

    def test_resets_player_states(self):
        engine = _make_engine()
        for p in engine.table.players.values():
            p.status = "folded"
            p.current_bet = 100
            p.total_in = 200
            p.hole_cards = [_c(R.ACE, S)]
        engine.end_hand()
        for p in engine.table.players.values():
            assert p.status == "active"
            assert p.current_bet == 0
            assert p.total_in == 0
            assert p.hole_cards == []

    def test_sets_phase_between_hands(self):
        engine = _make_engine()
        engine.table.phase = "showdown"
        engine.end_hand()
        assert engine.table.phase == "between_hands"

    def test_clears_side_pots(self):
        engine = _make_engine()
        engine.table.side_pots = [SidePot(amount=100, eligible_players={"A"})]
        engine.end_hand()
        assert engine.table.side_pots == []


# ===================================================================
# 6. Vote resolution
# ===================================================================

class TestVoteResolution:

    def test_vote_passes_swaps_rules(self):
        engine = _make_engine()
        proposed = TableRules(variant="shortdeck", betting="no_limit", small_blind=50, big_blind=100)
        engine.table.pending_vote = ModeVote(
            proposed_rules=proposed,
            proposed_by="A",
            votes_for={"A", "B"},
            votes_against={"C"},
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        engine.end_hand()
        assert engine.rules.variant == "shortdeck"
        assert engine.table.rules.variant == "shortdeck"
        assert engine.table.pending_vote is None
        assert isinstance(engine.variant, ShortdeckVariant)

    def test_vote_fails_on_tie(self):
        engine = _make_engine()
        proposed = TableRules(variant="shortdeck", betting="no_limit", small_blind=50, big_blind=100)
        engine.table.pending_vote = ModeVote(
            proposed_rules=proposed,
            proposed_by="A",
            votes_for={"A"},
            votes_against={"B"},
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        engine.end_hand()
        assert engine.rules.variant == "holdem"  # unchanged
        assert engine.table.pending_vote is None

    def test_vote_fails_against_majority(self):
        engine = _make_engine()
        proposed = TableRules(variant="shortdeck", betting="no_limit", small_blind=50, big_blind=100)
        engine.table.pending_vote = ModeVote(
            proposed_rules=proposed,
            proposed_by="A",
            votes_for={"A"},
            votes_against={"B", "C"},
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        engine.end_hand()
        assert engine.rules.variant == "holdem"

    def test_no_pending_vote_no_change(self):
        engine = _make_engine()
        engine.table.pending_vote = None
        engine.end_hand()
        assert engine.rules.variant == "holdem"

    def test_vote_from_shortdeck_to_holdem(self):
        rules = TableRules(variant="shortdeck", betting="no_limit", small_blind=50, big_blind=100)
        engine = _make_engine(rules=rules, variant=ShortdeckVariant())
        proposed = TableRules(variant="holdem", betting="no_limit", small_blind=50, big_blind=100)
        engine.table.pending_vote = ModeVote(
            proposed_rules=proposed,
            proposed_by="A",
            votes_for={"A", "B", "C"},
            votes_against=set(),
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        engine.end_hand()
        assert engine.rules.variant == "holdem"
        assert isinstance(engine.variant, HoldemVariant)


# ===================================================================
# 7. Shortdeck PLO — 4-player showdown with side pots
# ===================================================================

class TestShortdeckPLOShowdown:
    """
    Full 4-player Shortdeck PLO hand with three all-ins across streets,
    producing three side pots resolved independently.

    Hands:
      P1: Ad Kd 6s Td
      P2: Ah Qh 7c 8s
      P3: 8h 8d Tc 9s
      P4: Th Ts 9d 9c

    Board: 6d 7d Jd Qd 9h

    Betting (each player contributes 100 pre-flop):
      Flop  — P1 all-in +100  (total_in = 200); P2/P3/P4 call
      Turn  — P3 all-in +500  (total_in = 700); P2/P4 call
      River — P2 all-in +400  (total_in = 1100); P4 calls

    Side pots:
      Pot 1 (cap=200):  200×4 = 800   — all 4 eligible
      Pot 2 (cap=700):  500×3 = 1500  — P2, P3, P4 eligible
      Pot 3 (cap=1100): 400×2 = 800   — P2, P4 eligible

    Best PLO hands (must use exactly 2 hole + 3 community, shortdeck rankings):
      P1: {Ad,Kd} + {7d,Jd,Qd} → A-K-Q-J-7 flush (diamonds)   [flush > straight in shortdeck]
      P2: {Ah,8s} + {6d,7d,9h} → A-6-7-8-9 straight (high=9)
      P3: {Tc,8h} + {9h,Jd,Qd} → 8-9-T-J-Q straight (high=Q)
      P4: {9d,9c} + {9h,Jd,Qd} → set of 9s (three 9s, Q-J kickers)

    Winners:
      Pot 1 → P1 (flush beats all straights/trips)           wins  800
      Pot 2 → P3 (Q-high straight beats 9-high straight/trips) wins 1500
      Pot 3 → P2 (9-high straight beats set of 9s)           wins  800
      P4   → 0

    NOTE: Without the PLO constraint, P4 would make a full house
    (Th Ts 9d 9c 9h = 9s-full-of-Ts) which beats straights in shortdeck,
    producing wrong results. This test verifies that engine.showdown() uses
    the table's must_use_exactly_two_hole_cards rule correctly.
    """

    def _build_table(self) -> tuple["Table", "GameEngine"]:
        rules = TableRules(
            variant="shortdeck",
            betting="pot_limit",
            small_blind=1,
            big_blind=2,
            hole_cards_count=4,
            must_use_exactly_two_hole_cards=True,
        )

        def _p(sid, seat, total_in, status, hole_cards):
            p = Player(
                session_id=sid,
                name=sid,
                stack=0,
                hole_cards=hole_cards,
                seat=seat,
                status=status,
                total_in=total_in,
                joined_at=datetime(2025, 1, 1),
            )
            return p

        players = {
            "P1": _p("P1", 0, 200,  "all_in", [
                _c(R.ACE,   D), _c(R.KING,  D), _c(R.SIX,  S), _c(R.TEN,   D),
            ]),
            "P2": _p("P2", 1, 1100, "all_in", [
                _c(R.ACE,   H), _c(R.QUEEN, H), _c(R.SEVEN, C), _c(R.EIGHT, S),
            ]),
            "P3": _p("P3", 2, 700,  "all_in", [
                _c(R.EIGHT, H), _c(R.EIGHT, D), _c(R.TEN,   C), _c(R.NINE,  S),
            ]),
            "P4": _p("P4", 3, 1100, "active", [
                _c(R.TEN,   H), _c(R.TEN,   S), _c(R.NINE,  D), _c(R.NINE,  C),
            ]),
        }

        table = Table(
            table_id="test-plo-shortdeck",
            players=players,
            player_join_order=["P1", "P2", "P3", "P4"],
            admin_id="P1",
            rules=rules,
            board=Board(
                primary=[
                    _c(R.SIX,   D), _c(R.SEVEN, D), _c(R.JACK,  D),
                    _c(R.QUEEN, D), _c(R.NINE,  H),
                ],
            ),
            pot=3100,
            side_pots=[],
            deck=Deck.build("shortdeck"),
            dealer_seat=0,
            current_action_seat=0,
            phase="river",
        )

        engine = GameEngine(table, rules, ShortdeckVariant())
        return table, engine

    # ------------------------------------------------------------------
    # Side pot structure
    # ------------------------------------------------------------------

    def test_side_pot_amounts(self):
        """Three side pots are built with the correct amounts."""
        table, engine = self._build_table()
        from backend.game.betting import BettingEngine
        pots = BettingEngine.build_side_pots(table)
        amounts = [p.amount for p in pots]
        assert amounts == [800, 1500, 800]

    def test_side_pot_eligibility(self):
        """Each side pot has the correct eligible players."""
        table, engine = self._build_table()
        from backend.game.betting import BettingEngine
        pots = BettingEngine.build_side_pots(table)
        assert pots[0].eligible_players == {"P1", "P2", "P3", "P4"}
        assert pots[1].eligible_players == {"P2", "P3", "P4"}
        assert pots[2].eligible_players == {"P2", "P4"}

    # ------------------------------------------------------------------
    # Individual hand evaluations (PLO constraint enforced)
    # ------------------------------------------------------------------

    def test_p1_makes_flush_not_straight(self):
        """P1 best PLO hand: A-high diamond flush, not a straight."""
        from backend.game.hand_evaluator import HandEvaluator, HandRank
        table, engine = self._build_table()
        p1 = table.players["P1"]
        result = HandEvaluator.evaluate(p1.hole_cards, table.board.primary, table.rules)
        assert result.rank == HandRank.FLUSH

    def test_p2_makes_nine_high_straight(self):
        """P2 best PLO hand: A-6-7-8-9 shortdeck straight (high=9)."""
        from backend.game.hand_evaluator import HandEvaluator, HandRank
        table, engine = self._build_table()
        p2 = table.players["P2"]
        result = HandEvaluator.evaluate(p2.hole_cards, table.board.primary, table.rules)
        assert result.rank == HandRank.STRAIGHT
        assert result.tiebreaker[1] == 9

    def test_p3_makes_queen_high_straight(self):
        """P3 best PLO hand: 8-9-T-J-Q straight (high=Q=12)."""
        from backend.game.hand_evaluator import HandEvaluator, HandRank
        table, engine = self._build_table()
        p3 = table.players["P3"]
        result = HandEvaluator.evaluate(p3.hole_cards, table.board.primary, table.rules)
        assert result.rank == HandRank.STRAIGHT
        assert result.tiebreaker[1] == 12

    def test_p4_makes_set_not_full_house(self):
        """
        P4 PLO hand: set of 9s ({9d,9c} + {9h,Jd,Qd}).
        Without the PLO constraint P4 would freely use Th Ts 9d 9c 9h = full house,
        which beats straights in shortdeck. The PLO rule prevents this.
        """
        from backend.game.hand_evaluator import HandEvaluator, HandRank
        table, engine = self._build_table()
        p4 = table.players["P4"]
        result = HandEvaluator.evaluate(p4.hole_cards, table.board.primary, table.rules)
        assert result.rank == HandRank.THREE_OF_A_KIND
        assert result.rank != HandRank.FULL_HOUSE

    def test_p3_straight_beats_p2_straight(self):
        """Q-high straight (P3) beats 9-high straight (P2)."""
        from backend.game.hand_evaluator import HandEvaluator
        table, engine = self._build_table()
        r2 = HandEvaluator.evaluate(table.players["P2"].hole_cards, table.board.primary, table.rules)
        r3 = HandEvaluator.evaluate(table.players["P3"].hole_cards, table.board.primary, table.rules)
        assert HandEvaluator.compare(r3, r2) > 0

    def test_p1_flush_beats_p3_straight(self):
        """A-high flush (P1) beats Q-high straight (P3) — shortdeck flush > straight."""
        from backend.game.hand_evaluator import HandEvaluator
        table, engine = self._build_table()
        r1 = HandEvaluator.evaluate(table.players["P1"].hole_cards, table.board.primary, table.rules)
        r3 = HandEvaluator.evaluate(table.players["P3"].hole_cards, table.board.primary, table.rules)
        assert HandEvaluator.compare(r1, r3) > 0

    def test_p2_straight_beats_p4_set(self):
        """9-high straight (P2) beats set of 9s (P4) — shortdeck straight > trips."""
        from backend.game.hand_evaluator import HandEvaluator
        table, engine = self._build_table()
        r2 = HandEvaluator.evaluate(table.players["P2"].hole_cards, table.board.primary, table.rules)
        r4 = HandEvaluator.evaluate(table.players["P4"].hole_cards, table.board.primary, table.rules)
        assert HandEvaluator.compare(r2, r4) > 0

    # ------------------------------------------------------------------
    # Full showdown: chip distribution
    # ------------------------------------------------------------------

    def test_showdown_p1_wins_800(self):
        """P1 wins Pot 1 (800) with A-high flush."""
        _, engine = self._build_table()
        winnings = engine.showdown()
        assert winnings["P1"] == 800

    def test_showdown_p3_wins_1500(self):
        """P3 wins Pot 2 (1500) with Q-high straight."""
        _, engine = self._build_table()
        winnings = engine.showdown()
        assert winnings["P3"] == 1500

    def test_showdown_p2_wins_800(self):
        """P2 wins Pot 3 (800) with 9-high straight."""
        _, engine = self._build_table()
        winnings = engine.showdown()
        assert winnings["P2"] == 800

    def test_showdown_p4_wins_nothing(self):
        """P4 wins nothing — set of 9s loses to both straights."""
        _, engine = self._build_table()
        winnings = engine.showdown()
        assert winnings["P4"] == 0

    def test_showdown_total_chips_conserved(self):
        """All 3100 chips are distributed — none created or destroyed."""
        _, engine = self._build_table()
        winnings = engine.showdown()
        assert sum(winnings.values()) == 3100


# ===================================================================
# Max-capacity enforcement
# ===================================================================
# Card budget formula (no burn cards in current implementation):
#   max_players = (deck_size - community_cards) // hole_cards_count
#
# Deck sizes:  holdem=52, shortdeck=36
# Community:   single board=5 (3+1+1), extra_flop=8 (5 primary + 3 secondary flop)
# Hole cards:  holdem=2, PLO=4
#
# Derived limits:
#   PLO shortdeck  1 board  -> (36-5)//4  = 7
#   PLO shortdeck  2 boards -> (36-8)//4  = 7
#   PLO holdem     1 board  -> (52-5)//4  = 11 (schema cap of 9 applies)
#   PLO holdem     2 boards -> (52-8)//4  = 11 (schema cap of 9 applies)
#
# NOTE: If burn cards (3 per board) are ever introduced the limits become:
#   PLO shortdeck  1 board  -> (36-5-3)//4  = 7
#   PLO shortdeck  2 boards -> (36-10-6)//4 = 5
# ===================================================================

class TestTableRulesMaxCapacity:
    """Tests that TableRules.compute_max_players() returns the correct cap."""

    def test_plo_shortdeck_single_board_max_7(self):
        rules = TableRules(
            variant="shortdeck",
            betting="pot_limit",
            small_blind=50,
            big_blind=100,
            hole_cards_count=4,
            must_use_exactly_two_hole_cards=True,
            extra_flop=False,
        )
        assert rules.compute_max_players() == 7

    def test_plo_shortdeck_two_boards_max_7(self):
        rules = TableRules(
            variant="shortdeck",
            betting="pot_limit",
            small_blind=50,
            big_blind=100,
            hole_cards_count=4,
            must_use_exactly_two_hole_cards=True,
            extra_flop=True,
        )
        assert rules.compute_max_players() == 7

    def test_holdem_shortdeck_single_board_max_9(self):
        """Shortdeck holdem (2 hole cards): (36-5)//2=15, schema-capped to 9."""
        rules = TableRules(
            variant="shortdeck",
            betting="no_limit",
            small_blind=50,
            big_blind=100,
            hole_cards_count=2,
            extra_flop=False,
        )
        # Budget allows 15 but absolute maximum is 9.
        assert rules.compute_max_players() == 9

    def test_plo_holdem_single_board_max_9(self):
        """PLO holdem (4 hole cards): (52-5)//4=11, schema-capped to 9."""
        rules = TableRules(
            variant="holdem",
            betting="pot_limit",
            small_blind=50,
            big_blind=100,
            hole_cards_count=4,
            must_use_exactly_two_hole_cards=True,
            extra_flop=False,
        )
        assert rules.compute_max_players() == 9


class TestStartHandCardBudget:
    """start_hand() must not exhaust the deck when table is at computed capacity."""

    def _make_plo_shortdeck_engine(self, n_players: int, extra_flop: bool) -> GameEngine:
        rules = TableRules(
            variant="shortdeck",
            betting="pot_limit",
            small_blind=50,
            big_blind=100,
            hole_cards_count=4,
            must_use_exactly_two_hole_cards=True,
            extra_flop=extra_flop,
            max_players=n_players,
        )
        players = {
            str(i): _make_player(str(i), seat=i) for i in range(n_players)
        }
        table = _make_table(players, rules)
        variant = ShortdeckVariant()
        return GameEngine(table, rules, variant)

    def test_plo_shortdeck_7_players_deck_not_exhausted_after_deal(self):
        """7 PLO shortdeck players consume 7*4=28 hole cards; 36-28=8 left for 5 community."""
        engine = self._make_plo_shortdeck_engine(n_players=7, extra_flop=False)
        engine.start_hand()
        assert engine.table.deck.remaining >= 5  # enough for flop+turn+river

    def test_plo_shortdeck_8_players_deck_exhausted_before_community(self):
        """8 PLO shortdeck players consume 8*4=32 hole cards; only 4 remain — not enough for flop."""
        engine = self._make_plo_shortdeck_engine(n_players=8, extra_flop=False)
        engine.start_hand()
        # After dealing hole cards there are fewer than 5 cards left — community cannot be dealt.
        assert engine.table.deck.remaining < 5

    def test_plo_shortdeck_two_boards_7_players_deck_sufficient(self):
        """7 players × 4 cards = 28; 36-28=8 remaining covers 5+3=8 community cards exactly."""
        engine = self._make_plo_shortdeck_engine(n_players=7, extra_flop=True)
        engine.start_hand()
        from backend.game.table_rules import StreetConfig
        engine.deal_street(StreetConfig(name="flop", base_cards=3))
        engine.deal_street(StreetConfig(name="turn", base_cards=1))
        engine.deal_street(StreetConfig(name="river", base_cards=1))
        # All community cards dealt; both boards populated
        assert len(engine.table.board.primary) == 5
        assert len(engine.table.board.secondary) == 3

    def test_plo_shortdeck_two_boards_8_players_deck_exhausted(self):
        """8 players × 4 = 32 hole cards; only 4 left — cannot deal 5+3=8 community cards."""
        engine = self._make_plo_shortdeck_engine(n_players=8, extra_flop=True)
        engine.start_hand()
        assert engine.table.deck.remaining < 8
