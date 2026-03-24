"""Comprehensive round-trip serialization tests (to_dict / from_dict)."""

from datetime import datetime, timedelta

import pytest

from backend.game.betting import SidePot
from backend.game.card import Card, Rank, Suit
from backend.game.deck import Deck
from backend.game.player import Player
from backend.game.table import Board, ModeVote, Table
from backend.game.table_rules import TableRules


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(rank: Rank, suit: Suit) -> Card:
    return Card(rank, suit)


S, H, D, C = Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS
R = Rank


# ===================================================================
# 1. Card
# ===================================================================

class TestCardSerialization:

    def test_round_trip(self):
        card = _c(R.ACE, S)
        d = card.to_dict()
        restored = Card.from_dict(d)
        assert restored == card

    def test_dict_format(self):
        card = _c(R.TEN, H)
        d = card.to_dict()
        assert d == {"rank": 10, "suit": "h"}

    def test_all_suits(self):
        for suit in Suit:
            card = _c(R.KING, suit)
            assert Card.from_dict(card.to_dict()) == card

    def test_all_ranks(self):
        for rank in Rank:
            card = _c(rank, D)
            assert Card.from_dict(card.to_dict()) == card


# ===================================================================
# 2. Deck
# ===================================================================

class TestDeckSerialization:

    def test_holdem_round_trip(self):
        deck = Deck.build("holdem")
        d = deck.to_dict()
        restored = Deck.from_dict(d)
        assert restored.remaining == deck.remaining
        assert restored.to_list() == deck.to_list()

    def test_shortdeck_round_trip(self):
        deck = Deck.build("shortdeck")
        d = deck.to_dict()
        restored = Deck.from_dict(d)
        assert restored.remaining == 36
        assert restored.to_list() == deck.to_list()

    def test_partial_deck_after_deal(self):
        deck = Deck.build("holdem")
        deck.shuffle()
        deck.deal(5)
        d = deck.to_dict()
        restored = Deck.from_dict(d)
        assert restored.remaining == 47


# ===================================================================
# 3. Player
# ===================================================================

class TestPlayerSerialization:

    def test_round_trip(self):
        player = Player(
            session_id="abc",
            name="Alice",
            stack=1500,
            hole_cards=[_c(R.ACE, S), _c(R.KING, H)],
            seat=3,
            status="active",
            current_bet=100,
            total_in=200,
            is_admin=True,
            joined_at=datetime(2025, 6, 15, 12, 0, 0),
            disconnect_at=None,
        )
        d = player.to_dict()
        restored = Player.from_dict(d)
        assert restored.session_id == player.session_id
        assert restored.name == player.name
        assert restored.stack == player.stack
        assert restored.hole_cards == player.hole_cards
        assert restored.seat == player.seat
        assert restored.status == player.status
        assert restored.current_bet == player.current_bet
        assert restored.total_in == player.total_in
        assert restored.is_admin == player.is_admin
        assert restored.joined_at == player.joined_at
        assert restored.disconnect_at is None

    def test_with_disconnect_at(self):
        dt = datetime(2025, 6, 15, 12, 30, 0)
        player = Player(
            session_id="abc", name="Bob", stack=500,
            hole_cards=[], seat=0, disconnect_at=dt,
            joined_at=datetime(2025, 6, 15, 12, 0, 0),
        )
        d = player.to_dict()
        restored = Player.from_dict(d)
        assert restored.disconnect_at == dt

    def test_empty_hole_cards(self):
        player = Player(
            session_id="x", name="X", stack=100, hole_cards=[],
            seat=0, joined_at=datetime(2025, 1, 1),
        )
        d = player.to_dict()
        restored = Player.from_dict(d)
        assert restored.hole_cards == []


# ===================================================================
# 4. Board
# ===================================================================

class TestBoardSerialization:

    def test_empty_board(self):
        board = Board()
        d = board.to_dict()
        restored = Board.from_dict(d)
        assert restored.primary == []
        assert restored.secondary == []

    def test_board_with_primary(self):
        board = Board(
            primary=[_c(R.ACE, S), _c(R.KING, H), _c(R.QUEEN, D)],
        )
        d = board.to_dict()
        restored = Board.from_dict(d)
        assert restored.primary == board.primary

    def test_board_with_secondary(self):
        board = Board(
            primary=[_c(R.ACE, S), _c(R.KING, H), _c(R.QUEEN, D)],
            secondary=[_c(R.TEN, C), _c(R.NINE, S), _c(R.EIGHT, H)],
        )
        d = board.to_dict()
        restored = Board.from_dict(d)
        assert restored.primary == board.primary
        assert restored.secondary == board.secondary


# ===================================================================
# 5. ModeVote
# ===================================================================

class TestModeVoteSerialization:

    def test_round_trip(self):
        rules = TableRules(variant="shortdeck", betting="no_limit", small_blind=50, big_blind=100)
        vote = ModeVote(
            proposed_rules=rules,
            proposed_by="alice",
            votes_for={"alice", "bob"},
            votes_against={"charlie"},
            expires_at=datetime(2025, 6, 15, 13, 0, 0),
        )
        d = vote.to_dict()
        restored = ModeVote.from_dict(d)
        assert restored.proposed_rules.variant == "shortdeck"
        assert restored.proposed_by == "alice"
        assert restored.votes_for == {"alice", "bob"}
        assert restored.votes_against == {"charlie"}
        assert restored.expires_at == datetime(2025, 6, 15, 13, 0, 0)

    def test_empty_votes(self):
        rules = TableRules(variant="holdem", betting="no_limit", small_blind=1, big_blind=2)
        vote = ModeVote(
            proposed_rules=rules,
            proposed_by="x",
            votes_for=set(),
            votes_against=set(),
            expires_at=datetime(2025, 1, 1),
        )
        d = vote.to_dict()
        restored = ModeVote.from_dict(d)
        assert restored.votes_for == set()
        assert restored.votes_against == set()


# ===================================================================
# 6. TableRules
# ===================================================================

class TestTableRulesSerialization:

    def test_holdem_round_trip(self):
        rules = TableRules(
            variant="holdem", betting="no_limit", small_blind=50, big_blind=100,
            denomination="chips", hole_cards_count=2, extra_hole_card=False,
            must_use_exactly_two_hole_cards=False, extra_flop=False,
            street_modifiers={}, max_players=9, allow_rebuy=True,
        )
        d = rules.to_dict()
        restored = TableRules.from_dict(d)
        assert restored.variant == rules.variant
        assert restored.betting == rules.betting
        assert restored.small_blind == rules.small_blind
        assert restored.big_blind == rules.big_blind
        assert restored.denomination == rules.denomination
        assert restored.hole_cards_count == rules.hole_cards_count
        assert restored.extra_hole_card == rules.extra_hole_card
        assert restored.must_use_exactly_two_hole_cards == rules.must_use_exactly_two_hole_cards
        assert restored.extra_flop == rules.extra_flop
        assert restored.street_modifiers == rules.street_modifiers
        assert restored.max_players == rules.max_players
        assert restored.allow_rebuy == rules.allow_rebuy

    def test_shortdeck_with_modifiers(self):
        rules = TableRules(
            variant="shortdeck", betting="pot_limit", small_blind=25, big_blind=50,
            street_modifiers={"turn": 1, "river": 0},
            extra_flop=True, extra_hole_card=True,
            must_use_exactly_two_hole_cards=True,
            hole_cards_count=4, max_players=6,
        )
        d = rules.to_dict()
        restored = TableRules.from_dict(d)
        assert restored.variant == "shortdeck"
        assert restored.betting == "pot_limit"
        assert restored.street_modifiers == {"turn": 1, "river": 0}
        assert restored.extra_flop is True
        assert restored.extra_hole_card is True
        assert restored.must_use_exactly_two_hole_cards is True


# ===================================================================
# 7. SidePot
# ===================================================================

class TestSidePotSerialization:

    def test_round_trip(self):
        sp = SidePot(amount=500, eligible_players={"A", "B", "C"})
        d = sp.to_dict()
        restored = SidePot.from_dict(d)
        assert restored.amount == 500
        assert restored.eligible_players == {"A", "B", "C"}

    def test_single_player(self):
        sp = SidePot(amount=100, eligible_players={"X"})
        d = sp.to_dict()
        restored = SidePot.from_dict(d)
        assert restored.eligible_players == {"X"}


# ===================================================================
# 8. Table (full round trip including nested objects)
# ===================================================================

class TestTableSerialization:

    def _make_full_table(self) -> Table:
        rules = TableRules(
            variant="holdem", betting="no_limit", small_blind=50, big_blind=100,
            street_modifiers={"turn": 1},
        )
        players = {
            "alice": Player(
                session_id="alice", name="Alice", stack=1500,
                hole_cards=[_c(R.ACE, S), _c(R.KING, H)],
                seat=0, status="active", current_bet=100, total_in=200,
                is_admin=True, joined_at=datetime(2025, 6, 15, 12, 0, 0),
            ),
            "bob": Player(
                session_id="bob", name="Bob", stack=800,
                hole_cards=[_c(R.QUEEN, D), _c(R.JACK, C)],
                seat=1, status="active", current_bet=100, total_in=100,
                joined_at=datetime(2025, 6, 15, 12, 1, 0),
            ),
        }
        board = Board(
            primary=[_c(R.TEN, S), _c(R.NINE, H), _c(R.EIGHT, D)],
            secondary=[],
        )
        side_pots = [SidePot(amount=400, eligible_players={"alice", "bob"})]
        deck = Deck.build("holdem")
        proposed = TableRules(variant="shortdeck", betting="no_limit", small_blind=50, big_blind=100)
        vote = ModeVote(
            proposed_rules=proposed,
            proposed_by="alice",
            votes_for={"alice"},
            votes_against=set(),
            expires_at=datetime(2025, 6, 15, 13, 0, 0),
        )
        return Table(
            table_id="table-1",
            players=players,
            player_join_order=["alice", "bob"],
            admin_id="alice",
            rules=rules,
            board=board,
            pot=400,
            side_pots=side_pots,
            deck=deck,
            dealer_seat=0,
            current_action_seat=1,
            phase="flop",
            hand_number=5,
            action_seq=12,
            pending_vote=vote,
        )

    def test_full_round_trip(self):
        table = self._make_full_table()
        d = table.to_dict()
        restored = Table.from_dict(d)

        assert restored.table_id == "table-1"
        assert restored.admin_id == "alice"
        assert restored.pot == 400
        assert restored.dealer_seat == 0
        assert restored.current_action_seat == 1
        assert restored.phase == "flop"
        assert restored.hand_number == 5
        assert restored.action_seq == 12

        # Players
        assert set(restored.players.keys()) == {"alice", "bob"}
        assert restored.players["alice"].stack == 1500
        assert restored.players["alice"].hole_cards == [_c(R.ACE, S), _c(R.KING, H)]
        assert restored.players["bob"].seat == 1

        # Board
        assert len(restored.board.primary) == 3
        assert restored.board.primary[0] == _c(R.TEN, S)

        # Side pots
        assert len(restored.side_pots) == 1
        assert restored.side_pots[0].amount == 400

        # Rules
        assert restored.rules.variant == "holdem"
        assert restored.rules.street_modifiers == {"turn": 1}

        # Deck
        assert restored.deck.remaining == 52

        # Vote
        assert restored.pending_vote is not None
        assert restored.pending_vote.proposed_rules.variant == "shortdeck"
        assert restored.pending_vote.proposed_by == "alice"

    def test_round_trip_no_vote(self):
        table = self._make_full_table()
        table.pending_vote = None
        d = table.to_dict()
        restored = Table.from_dict(d)
        assert restored.pending_vote is None

    def test_round_trip_empty_side_pots(self):
        table = self._make_full_table()
        table.side_pots = []
        d = table.to_dict()
        restored = Table.from_dict(d)
        assert restored.side_pots == []

    def test_player_join_order_preserved(self):
        table = self._make_full_table()
        d = table.to_dict()
        restored = Table.from_dict(d)
        assert restored.player_join_order == ["alice", "bob"]
