"""Comprehensive tests for hand_evaluator.py — HandRank, HandResult, _evaluate_5, HandEvaluator."""

import pytest

from backend.game.card import Card, Rank, Suit
from backend.game.hand_evaluator import (
    HandEvaluator,
    HandRank,
    HandResult,
    _evaluate_5,
)
from backend.game.table_rules import TableRules


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(rank: Rank, suit: Suit) -> Card:
    return Card(rank, suit)


S, H, D, C = Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS
R = Rank


def _holdem_rules(**overrides) -> TableRules:
    defaults = dict(variant="holdem", betting="no_limit", small_blind=1, big_blind=2)
    defaults.update(overrides)
    return TableRules(**defaults)


def _shortdeck_rules(**overrides) -> TableRules:
    defaults = dict(variant="shortdeck", betting="no_limit", small_blind=1, big_blind=2)
    defaults.update(overrides)
    return TableRules(**defaults)


# ===================================================================
# 1. Holdem hand detection — known 5-card hands via _evaluate_5
# ===================================================================

class TestEvaluate5HoldemHands:
    """Test that _evaluate_5 correctly classifies every hand rank."""

    def test_royal_flush(self):
        cards = [_c(R.ACE, S), _c(R.KING, S), _c(R.QUEEN, S), _c(R.JACK, S), _c(R.TEN, S)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.ROYAL_FLUSH

    def test_straight_flush(self):
        cards = [_c(R.NINE, H), _c(R.EIGHT, H), _c(R.SEVEN, H), _c(R.SIX, H), _c(R.FIVE, H)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.STRAIGHT_FLUSH
        assert result.tiebreaker[1] == 9

    def test_four_of_a_kind(self):
        cards = [_c(R.ACE, S), _c(R.ACE, H), _c(R.ACE, D), _c(R.ACE, C), _c(R.KING, S)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.FOUR_OF_A_KIND

    def test_full_house(self):
        cards = [_c(R.KING, S), _c(R.KING, H), _c(R.KING, D), _c(R.NINE, S), _c(R.NINE, H)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.FULL_HOUSE

    def test_flush(self):
        cards = [_c(R.ACE, D), _c(R.JACK, D), _c(R.NINE, D), _c(R.SEVEN, D), _c(R.THREE, D)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.FLUSH

    def test_straight(self):
        cards = [_c(R.TEN, S), _c(R.NINE, H), _c(R.EIGHT, D), _c(R.SEVEN, C), _c(R.SIX, S)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.STRAIGHT
        assert result.tiebreaker[1] == 10

    def test_three_of_a_kind(self):
        cards = [_c(R.QUEEN, S), _c(R.QUEEN, H), _c(R.QUEEN, D), _c(R.ACE, S), _c(R.KING, H)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.THREE_OF_A_KIND

    def test_two_pair(self):
        cards = [_c(R.ACE, S), _c(R.ACE, H), _c(R.KING, D), _c(R.KING, C), _c(R.QUEEN, S)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.TWO_PAIR

    def test_one_pair(self):
        cards = [_c(R.JACK, S), _c(R.JACK, H), _c(R.ACE, D), _c(R.KING, C), _c(R.QUEEN, S)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.ONE_PAIR

    def test_high_card(self):
        cards = [_c(R.ACE, S), _c(R.KING, H), _c(R.QUEEN, D), _c(R.JACK, C), _c(R.NINE, S)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.HIGH_CARD

    def test_variant_field_holdem(self):
        cards = [_c(R.ACE, S), _c(R.KING, H), _c(R.QUEEN, D), _c(R.JACK, C), _c(R.NINE, S)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.variant == "holdem"

    def test_variant_field_shortdeck(self):
        cards = [_c(R.ACE, S), _c(R.KING, H), _c(R.QUEEN, D), _c(R.JACK, C), _c(R.NINE, S)]
        result = _evaluate_5(cards, shortdeck=True)
        assert result.variant == "shortdeck"


# ===================================================================
# 2. Ace-low straights
# ===================================================================

class TestAceLowStraights:

    def test_holdem_ace_low_straight(self):
        """A-2-3-4-5 is a valid straight in holdem with high=5."""
        cards = [_c(R.ACE, S), _c(R.TWO, H), _c(R.THREE, D), _c(R.FOUR, C), _c(R.FIVE, S)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.STRAIGHT
        assert result.tiebreaker[1] == 5

    def test_shortdeck_ace_low_straight(self):
        """A-6-7-8-9 is a valid straight in shortdeck with high=9."""
        cards = [_c(R.ACE, S), _c(R.SIX, H), _c(R.SEVEN, D), _c(R.EIGHT, C), _c(R.NINE, S)]
        result = _evaluate_5(cards, shortdeck=True)
        assert result.rank == HandRank.STRAIGHT
        assert result.tiebreaker[1] == 9

    def test_shortdeck_no_holdem_wheel(self):
        """A-6-7-8-T is NOT a straight in shortdeck (gap at 9)."""
        cards = [_c(R.ACE, S), _c(R.SIX, H), _c(R.SEVEN, D), _c(R.EIGHT, C), _c(R.TEN, S)]
        result = _evaluate_5(cards, shortdeck=True)
        assert result.rank != HandRank.STRAIGHT

    def test_holdem_ace_low_straight_flush(self):
        """A-2-3-4-5 suited is a straight flush in holdem."""
        cards = [_c(R.ACE, H), _c(R.TWO, H), _c(R.THREE, H), _c(R.FOUR, H), _c(R.FIVE, H)]
        result = _evaluate_5(cards, shortdeck=False)
        assert result.rank == HandRank.STRAIGHT_FLUSH

    def test_shortdeck_ace_low_straight_flush(self):
        """A-6-7-8-9 suited is a straight flush in shortdeck."""
        cards = [_c(R.ACE, D), _c(R.SIX, D), _c(R.SEVEN, D), _c(R.EIGHT, D), _c(R.NINE, D)]
        result = _evaluate_5(cards, shortdeck=True)
        assert result.rank == HandRank.STRAIGHT_FLUSH


# ===================================================================
# 3. Shortdeck ranking order — flush beats full house
# ===================================================================

class TestShortdeckRankingOrder:

    def test_flush_beats_full_house_in_shortdeck(self):
        flush_cards = [_c(R.ACE, D), _c(R.KING, D), _c(R.NINE, D), _c(R.SEVEN, D), _c(R.SIX, D)]
        fh_cards = [_c(R.KING, S), _c(R.KING, H), _c(R.KING, C), _c(R.NINE, S), _c(R.NINE, H)]

        flush_result = _evaluate_5(flush_cards, shortdeck=True)
        fh_result = _evaluate_5(fh_cards, shortdeck=True)

        assert flush_result.rank == HandRank.FLUSH
        assert fh_result.rank == HandRank.FULL_HOUSE
        assert flush_result.effective_rank() > fh_result.effective_rank()
        assert HandEvaluator.compare(flush_result, fh_result) > 0

    def test_full_house_beats_flush_in_holdem(self):
        flush_cards = [_c(R.ACE, D), _c(R.JACK, D), _c(R.NINE, D), _c(R.SEVEN, D), _c(R.THREE, D)]
        fh_cards = [_c(R.KING, S), _c(R.KING, H), _c(R.KING, D), _c(R.NINE, S), _c(R.NINE, H)]

        flush_result = _evaluate_5(flush_cards, shortdeck=False)
        fh_result = _evaluate_5(fh_cards, shortdeck=False)

        assert fh_result.effective_rank() > flush_result.effective_rank()
        assert HandEvaluator.compare(fh_result, flush_result) > 0

    def test_effective_rank_shortdeck_order(self):
        """Verify shortdeck ordering: flush(7) > full_house(6)."""
        flush_result = HandResult(
            rank=HandRank.FLUSH, tiebreaker=[6, 14, 13, 9, 7, 6],
            best_cards=[], variant="shortdeck",
        )
        fh_result = HandResult(
            rank=HandRank.FULL_HOUSE, tiebreaker=[7, 13, 9],
            best_cards=[], variant="shortdeck",
        )
        assert flush_result.effective_rank() == 7
        assert fh_result.effective_rank() == 6


# ===================================================================
# 4. HandEvaluator.compare
# ===================================================================

class TestHandEvaluatorCompare:

    def test_higher_rank_wins(self):
        flush = _evaluate_5(
            [_c(R.ACE, D), _c(R.JACK, D), _c(R.NINE, D), _c(R.SEVEN, D), _c(R.THREE, D)],
            shortdeck=False,
        )
        pair = _evaluate_5(
            [_c(R.ACE, S), _c(R.ACE, H), _c(R.KING, D), _c(R.QUEEN, C), _c(R.JACK, S)],
            shortdeck=False,
        )
        assert HandEvaluator.compare(flush, pair) > 0
        assert HandEvaluator.compare(pair, flush) < 0

    def test_same_rank_better_kickers_win(self):
        pair_ak = _evaluate_5(
            [_c(R.ACE, S), _c(R.ACE, H), _c(R.KING, D), _c(R.QUEEN, C), _c(R.JACK, S)],
            shortdeck=False,
        )
        pair_aq = _evaluate_5(
            [_c(R.ACE, D), _c(R.ACE, C), _c(R.QUEEN, S), _c(R.JACK, H), _c(R.TEN, D)],
            shortdeck=False,
        )
        assert HandEvaluator.compare(pair_ak, pair_aq) > 0

    def test_identical_hands_return_zero(self):
        cards_a = [_c(R.ACE, S), _c(R.KING, H), _c(R.QUEEN, D), _c(R.JACK, C), _c(R.NINE, S)]
        cards_b = [_c(R.ACE, H), _c(R.KING, D), _c(R.QUEEN, C), _c(R.JACK, S), _c(R.NINE, H)]
        result_a = _evaluate_5(cards_a, shortdeck=False)
        result_b = _evaluate_5(cards_b, shortdeck=False)
        assert HandEvaluator.compare(result_a, result_b) == 0

    def test_compare_two_pair_high_pair_wins(self):
        aa_kk = _evaluate_5(
            [_c(R.ACE, S), _c(R.ACE, H), _c(R.KING, D), _c(R.KING, C), _c(R.TWO, S)],
            shortdeck=False,
        )
        kk_qq = _evaluate_5(
            [_c(R.KING, S), _c(R.KING, H), _c(R.QUEEN, D), _c(R.QUEEN, C), _c(R.ACE, S)],
            shortdeck=False,
        )
        assert HandEvaluator.compare(aa_kk, kk_qq) > 0

    def test_compare_straights_higher_top_wins(self):
        high_straight = _evaluate_5(
            [_c(R.TEN, S), _c(R.NINE, H), _c(R.EIGHT, D), _c(R.SEVEN, C), _c(R.SIX, S)],
            shortdeck=False,
        )
        low_straight = _evaluate_5(
            [_c(R.NINE, D), _c(R.EIGHT, C), _c(R.SEVEN, S), _c(R.SIX, H), _c(R.FIVE, D)],
            shortdeck=False,
        )
        assert HandEvaluator.compare(high_straight, low_straight) > 0


# ===================================================================
# 5. HandEvaluator.evaluate with 7 cards (best 5 of 7)
# ===================================================================

class TestEvaluateBestOf7:

    def test_royal_flush_from_7_cards(self):
        rules = _holdem_rules()
        hole = [_c(R.ACE, H), _c(R.KING, H)]
        community = [_c(R.QUEEN, H), _c(R.JACK, H), _c(R.TEN, H), _c(R.TWO, C), _c(R.THREE, D)]
        result = HandEvaluator.evaluate(hole, community, rules)
        assert result.rank == HandRank.ROYAL_FLUSH

    def test_four_of_a_kind_from_7_cards(self):
        rules = _holdem_rules()
        hole = [_c(R.TWO, C), _c(R.TWO, D)]
        community = [_c(R.TWO, H), _c(R.TWO, S), _c(R.ACE, C), _c(R.KING, D), _c(R.QUEEN, H)]
        result = HandEvaluator.evaluate(hole, community, rules)
        assert result.rank == HandRank.FOUR_OF_A_KIND

    def test_picks_best_five_flush(self):
        rules = _holdem_rules()
        hole = [_c(R.ACE, D), _c(R.KING, D)]
        community = [_c(R.TEN, D), _c(R.NINE, D), _c(R.EIGHT, D), _c(R.TWO, C), _c(R.THREE, H)]
        result = HandEvaluator.evaluate(hole, community, rules)
        assert result.rank == HandRank.FLUSH
        assert all(card.suit == Suit.DIAMONDS for card in result.best_cards)


# ===================================================================
# 6. PLO mode — must_use_exactly_two_hole_cards
# ===================================================================

class TestPLOMode:

    def test_plo_royal_flush(self):
        """PLO: must use exactly 2 hole + 3 community."""
        rules = _holdem_rules(must_use_exactly_two_hole_cards=True, hole_cards_count=4)
        hole = [_c(R.ACE, H), _c(R.KING, H), _c(R.QUEEN, D), _c(R.TWO, C)]
        community = [_c(R.QUEEN, H), _c(R.JACK, H), _c(R.TEN, H), _c(R.THREE, D), _c(R.FOUR, C)]
        result = HandEvaluator.evaluate(hole, community, rules)
        # Best PLO hand: Ah Kh (hole) + Qh Jh Th (community) = Royal Flush
        assert result.rank == HandRank.ROYAL_FLUSH

    def test_plo_cannot_use_four_community(self):
        """PLO restriction prevents using 4+ community cards even when they make a better hand."""
        rules = _holdem_rules(must_use_exactly_two_hole_cards=True, hole_cards_count=4)
        # Community has 4 hearts forming a flush; hole has only 1 heart.
        hole = [_c(R.ACE, H), _c(R.TWO, C), _c(R.THREE, D), _c(R.FOUR, S)]
        community = [_c(R.KING, H), _c(R.QUEEN, H), _c(R.JACK, H), _c(R.TEN, H), _c(R.NINE, C)]
        result = HandEvaluator.evaluate(hole, community, rules)
        # Cannot make flush in PLO (only 1 heart in hole, need exactly 2 hole cards)
        assert result.rank not in (HandRank.FLUSH, HandRank.STRAIGHT_FLUSH, HandRank.ROYAL_FLUSH)

    def test_plo_selects_best_combination(self):
        """PLO evaluator tries all C(4,2)*C(5,3) combos and picks the best."""
        rules = _holdem_rules(must_use_exactly_two_hole_cards=True, hole_cards_count=4)
        # Hole: As Ks Qd Jd  Community: Ts 9s 8s 2c 3h
        # Best 2-hole combo: As Ks + Ts 9s 8s = flush (A-high spades)
        hole = [_c(R.ACE, S), _c(R.KING, S), _c(R.QUEEN, D), _c(R.JACK, D)]
        community = [_c(R.TEN, S), _c(R.NINE, S), _c(R.EIGHT, S), _c(R.TWO, C), _c(R.THREE, H)]
        result = HandEvaluator.evaluate(hole, community, rules)
        assert result.rank == HandRank.FLUSH


# ===================================================================
# 7. PLO — must use exactly two hole cards (edge cases)
# ===================================================================

class TestPLOMustUseTwoHoleCards:
    """
    These tests verify that the PLO constraint (exactly 2 hole + 3 community)
    prevents hands that would be valid in standard mode.
    """

    def test_holdem_plo_four_aces_hole_low_board_is_pair(self):
        """
        Hole: Ad Ac As Ah  Board: 2h 3h 4h 5h 6h
        In PLO you must use exactly 2 hole cards — so the hand is always AA + 3
        community cards. You cannot form quads, a straight, a flush, or a
        straight flush because the hole contributes only two Aces.
        Expected: ONE_PAIR (Aces).
        """
        rules = _holdem_rules(must_use_exactly_two_hole_cards=True, hole_cards_count=4)
        hole = [_c(R.ACE, D), _c(R.ACE, C), _c(R.ACE, S), _c(R.ACE, H)]
        community = [_c(R.TWO, H), _c(R.THREE, H), _c(R.FOUR, H), _c(R.FIVE, H), _c(R.SIX, H)]
        result = HandEvaluator.evaluate(hole, community, rules)
        assert result.rank == HandRank.ONE_PAIR
        assert result.rank not in (
            HandRank.FOUR_OF_A_KIND,
            HandRank.STRAIGHT_FLUSH,
            HandRank.FLUSH,
            HandRank.STRAIGHT,
        )

    def test_shortdeck_plo_four_aces_hole_straight_flush_board_is_pair(self):
        """
        Hole: Ad Ac As Ah  Board: 6h 7h 8h 9h Th  (shortdeck)
        Same logic — only 1 heart in hole (Ah), so no flush is possible with
        exactly 2 hole cards. No straight either (AA + any 3 from board is still
        just a pair). Quads impossible.
        Expected: ONE_PAIR (Aces).
        """
        rules = _shortdeck_rules(must_use_exactly_two_hole_cards=True, hole_cards_count=4)
        hole = [_c(R.ACE, D), _c(R.ACE, C), _c(R.ACE, S), _c(R.ACE, H)]
        community = [_c(R.SIX, H), _c(R.SEVEN, H), _c(R.EIGHT, H), _c(R.NINE, H), _c(R.TEN, H)]
        result = HandEvaluator.evaluate(hole, community, rules)
        assert result.rank == HandRank.ONE_PAIR
        assert result.rank not in (
            HandRank.FOUR_OF_A_KIND,
            HandRank.STRAIGHT_FLUSH,
            HandRank.FLUSH,
            HandRank.STRAIGHT,
        )

    def test_shortdeck_plo_ace_nine_hole_makes_nine_high_straight(self):
        """
        Hole: Ad Ac As 9h  Board: 6h 7h 8h Th  (shortdeck, 4 community cards)
        Best PLO combination: {As, 9h} (hole) + {6h, 7h, 8h} (community)
          → A-6-7-8-9 = the shortdeck ace-low straight (high card = 9).
        Other hole combos ({Ad,Ac}, {Ad,As}, etc.) contribute AA + 3 board cards
        which is just a pair — so the straight is the winner.
        Expected: STRAIGHT with tiebreaker high = 9.
        """
        rules = _shortdeck_rules(must_use_exactly_two_hole_cards=True, hole_cards_count=4)
        hole = [_c(R.ACE, D), _c(R.ACE, C), _c(R.ACE, S), _c(R.NINE, H)]
        community = [_c(R.SIX, H), _c(R.SEVEN, H), _c(R.EIGHT, H), _c(R.TEN, H)]
        result = HandEvaluator.evaluate(hole, community, rules)
        assert result.rank == HandRank.STRAIGHT
        assert result.tiebreaker[1] == 9


# ===================================================================
# 8. HandEvaluator.find_winners
# ===================================================================

class TestFindWinners:

    def test_single_winner(self):
        flush = _evaluate_5(
            [_c(R.ACE, D), _c(R.JACK, D), _c(R.NINE, D), _c(R.SEVEN, D), _c(R.THREE, D)],
            shortdeck=False,
        )
        pair = _evaluate_5(
            [_c(R.ACE, S), _c(R.ACE, H), _c(R.KING, D), _c(R.QUEEN, C), _c(R.JACK, S)],
            shortdeck=False,
        )
        results = {"alice": flush, "bob": pair}
        winners = HandEvaluator.find_winners(results)
        assert winners == ["alice"]

    def test_tie_returns_both(self):
        hand_a = _evaluate_5(
            [_c(R.ACE, S), _c(R.KING, H), _c(R.QUEEN, D), _c(R.JACK, C), _c(R.NINE, S)],
            shortdeck=False,
        )
        hand_b = _evaluate_5(
            [_c(R.ACE, H), _c(R.KING, D), _c(R.QUEEN, C), _c(R.JACK, S), _c(R.NINE, H)],
            shortdeck=False,
        )
        results = {"alice": hand_a, "bob": hand_b}
        winners = HandEvaluator.find_winners(results)
        assert set(winners) == {"alice", "bob"}

    def test_multiple_players_clear_best(self):
        royal = _evaluate_5(
            [_c(R.ACE, S), _c(R.KING, S), _c(R.QUEEN, S), _c(R.JACK, S), _c(R.TEN, S)],
            shortdeck=False,
        )
        pair = _evaluate_5(
            [_c(R.ACE, H), _c(R.ACE, D), _c(R.KING, C), _c(R.QUEEN, H), _c(R.JACK, D)],
            shortdeck=False,
        )
        high = _evaluate_5(
            [_c(R.ACE, C), _c(R.KING, H), _c(R.QUEEN, D), _c(R.JACK, C), _c(R.NINE, D)],
            shortdeck=False,
        )
        results = {"alice": royal, "bob": pair, "charlie": high}
        winners = HandEvaluator.find_winners(results)
        assert winners == ["alice"]

    def test_empty_returns_empty(self):
        assert HandEvaluator.find_winners({}) == []


# ===================================================================
# 8. Evaluate via full HandEvaluator.evaluate (7-card holdem path)
# ===================================================================

class TestEvaluateViaFullAPI:
    """Tests using the public HandEvaluator.evaluate with hole+community (7 cards)."""

    def test_holdem_straight_ace_low_7card(self):
        rules = _holdem_rules()
        hole = [_c(R.ACE, S), _c(R.TWO, H)]
        community = [_c(R.THREE, D), _c(R.FOUR, C), _c(R.FIVE, H), _c(R.NINE, S), _c(R.TEN, D)]
        result = HandEvaluator.evaluate(hole, community, rules)
        assert result.rank == HandRank.STRAIGHT

    def test_shortdeck_a6789_7card(self):
        rules = _shortdeck_rules()
        hole = [_c(R.ACE, S), _c(R.SIX, H)]
        community = [_c(R.SEVEN, D), _c(R.EIGHT, C), _c(R.NINE, H), _c(R.JACK, S), _c(R.KING, D)]
        result = HandEvaluator.evaluate(hole, community, rules)
        assert result.rank == HandRank.STRAIGHT

    def test_shortdeck_flush_beats_full_house_7card(self):
        rules = _shortdeck_rules()
        fh_hole = [_c(R.TEN, S), _c(R.TEN, H)]
        fh_comm = [_c(R.TEN, D), _c(R.SEVEN, C), _c(R.SEVEN, H), _c(R.EIGHT, D), _c(R.NINE, C)]
        fh = HandEvaluator.evaluate(fh_hole, fh_comm, rules)
        assert fh.rank == HandRank.FULL_HOUSE

        flush_hole = [_c(R.ACE, H), _c(R.KING, H)]
        flush_comm = [_c(R.NINE, H), _c(R.EIGHT, H), _c(R.SIX, H), _c(R.TEN, S), _c(R.JACK, D)]
        flush = HandEvaluator.evaluate(flush_hole, flush_comm, rules)
        assert flush.rank == HandRank.FLUSH

        assert HandEvaluator.compare(flush, fh) == 1

    def test_kicker_comparison_via_evaluate(self):
        rules = _holdem_rules()
        hole1 = [_c(R.ACE, H), _c(R.KING, H)]
        hole2 = [_c(R.QUEEN, H), _c(R.JACK, H)]
        community = [_c(R.EIGHT, C), _c(R.EIGHT, D), _c(R.TWO, S), _c(R.THREE, H), _c(R.SEVEN, D)]
        r1 = HandEvaluator.evaluate(hole1, community, rules)
        r2 = HandEvaluator.evaluate(hole2, community, rules)
        assert r1.rank == HandRank.ONE_PAIR
        assert r2.rank == HandRank.ONE_PAIR
        assert HandEvaluator.compare(r1, r2) == 1  # AK kickers beat QJ


# ===================================================================
# 9. Double board PLO Shortdeck — 3-player all-in pot distribution
# ===================================================================

class TestDoubleBoardPLOShortdeck:
    """
    3-player PLO shortdeck hand with two boards and side pot.

    Setup:
      P1 (UTG):  Ad Ac 8d 9s
      P2 (BTN):  Kd Qd Th 9h
      P3 (CO):   6h 6s 6d Td

    Pre-flop action: 200 chips each → 600 total
      P1 all-in for 400 more  (total_in = 600)
      P2 all-in for 800 more  (total_in = 1000)
      P3 calls 800 more       (total_in = 1000)
    Grand total pot: 2600

    Side-pot structure (standard algorithm):
      Main pot  (capped at P1's 600): 600 × 3 = 1800  — all three eligible
      Side pot  (400 × 2):             400 × 2 =  800  — P2 & P3 only

    Board 1: 8c 9c 7c 6c Kc  (all clubs)
      P1 (Ad+9s + 6c+7c+8c): A-6-7-8-9 shortdeck ace-low straight (high=9)  → STRAIGHT
      P2 (Th+9h + 6c+7c+8c): 6-7-8-9-T straight (high=10)                  → STRAIGHT
      P3 (6d+Td + 6c+7c+8c ... or Td+9h? — best: 6s+Td+7c+8c+9c): 6-7-8-9-T → STRAIGHT
      P2 and P3 share the T-high straight; P1 has a lower 9-high (A-6-7-8-9).
      → P2 and P3 tie on board 1; P1 loses board 1.

    Board 2: Tc Ts Jd 7d 9d
      P1 (Ad+8d + Jd+7d+9d):   A-high diamond flush (A J 9 8 7)    → FLUSH
      P2 (Kd+Qd + Jd+7d+9d):   K-high diamond flush (K Q J 9 7)    → FLUSH
      P3 (6x+Th + Tc+Ts+Jd):   three Tens (T T T 6 J)              → THREE_OF_A_KIND
      Note: P3 cannot make a full house under PLO rules — board 2 has no 6,
      so the PLO constraint (exactly 2 hole + 3 community) prevents pairing
      the trip Tens with a pair of 6s. P1 holds the best flush (A-high).
      → P1 wins board 2 main; P2 wins board 2 side (K-high flush beats P3).

    Payout (each board = half the relevant pot):
      Board 1 — main (900): P2 & P3 tie → 450 each; P1 gets 0
               side (400): P2 & P3 tie → 200 each
      Board 2 — main (900): P1 wins → 900
               side (400): P1 not eligible; P2 beats P3 → P2 gets 400
      P1 total: 0 + 900           =  900
      P2 total: 450 + 200 + 400   = 1050
      P3 total: 450 + 200         =  650
      Grand total: 900 + 1050 + 650 = 2600  ✓
    """

    def setup_method(self):
        self.rules = _shortdeck_rules(
            must_use_exactly_two_hole_cards=True,
            hole_cards_count=4,
        )
        # Hole cards — note Td/Th are swapped vs. original scenario so that
        # P2 holds Td (giving a K-high diamond flush on board 2) and P3 holds
        # Th (giving three-of-a-kind Tens, the best P3 can make on board 2
        # under PLO rules since board 2 contains no 6 to pair with hole sixes).
        self.p1_hole = [_c(R.ACE, D), _c(R.ACE, C), _c(R.EIGHT, D), _c(R.NINE, S)]
        self.p2_hole = [_c(R.KING, D), _c(R.QUEEN, D), _c(R.TEN, D), _c(R.NINE, H)]
        self.p3_hole = [_c(R.SIX, H), _c(R.SIX, S), _c(R.SIX, D), _c(R.TEN, H)]
        # Boards
        self.board1 = [_c(R.EIGHT, C), _c(R.NINE, C), _c(R.SEVEN, C), _c(R.SIX, C), _c(R.KING, C)]
        self.board2 = [_c(R.TEN, C), _c(R.TEN, S), _c(R.JACK, D), _c(R.SEVEN, D), _c(R.NINE, D)]
        # Chip contributions
        self.p1_total_in = 600   # 200 pre + 400 all-in
        self.p2_total_in = 1000  # 200 pre + 800 (400+400)
        self.p3_total_in = 1000  # 200 pre + 800 call
        self.grand_pot   = 2600

    # --- Board 1 hand ranks ---

    def test_board1_p1_ace_low_straight(self):
        """P1 makes the A-6-7-8-9 shortdeck ace-low straight (high=9) on board 1."""
        result = HandEvaluator.evaluate(self.p1_hole, self.board1, self.rules)
        assert result.rank == HandRank.STRAIGHT
        assert result.tiebreaker[1] == 9

    def test_board1_p2_ten_high_straight(self):
        """P2 makes the 6-7-8-9-T straight (high=10) on board 1."""
        result = HandEvaluator.evaluate(self.p2_hole, self.board1, self.rules)
        assert result.rank == HandRank.STRAIGHT
        assert result.tiebreaker[1] == 10

    def test_board1_p3_ten_high_straight(self):
        """P3 makes the 6-7-8-9-T straight (high=10) on board 1."""
        result = HandEvaluator.evaluate(self.p3_hole, self.board1, self.rules)
        assert result.rank == HandRank.STRAIGHT
        assert result.tiebreaker[1] == 10

    def test_board1_p2_p3_tie(self):
        """P2 and P3 tie on board 1 with identical T-high straights."""
        r2 = HandEvaluator.evaluate(self.p2_hole, self.board1, self.rules)
        r3 = HandEvaluator.evaluate(self.p3_hole, self.board1, self.rules)
        assert HandEvaluator.compare(r2, r3) == 0
        winners = HandEvaluator.find_winners({"p2": r2, "p3": r3})
        assert set(winners) == {"p2", "p3"}

    def test_board1_p2_beats_p1(self):
        """P2's T-high straight beats P1's 9-high (ace-low) straight on board 1."""
        r1 = HandEvaluator.evaluate(self.p1_hole, self.board1, self.rules)
        r2 = HandEvaluator.evaluate(self.p2_hole, self.board1, self.rules)
        assert HandEvaluator.compare(r2, r1) > 0

    def test_board1_winners_are_p2_and_p3(self):
        """Board 1 is won by P2 and P3; P1 has the inferior ace-low straight."""
        r1 = HandEvaluator.evaluate(self.p1_hole, self.board1, self.rules)
        r2 = HandEvaluator.evaluate(self.p2_hole, self.board1, self.rules)
        r3 = HandEvaluator.evaluate(self.p3_hole, self.board1, self.rules)
        winners = HandEvaluator.find_winners({"p1": r1, "p2": r2, "p3": r3})
        assert set(winners) == {"p2", "p3"}

    # --- Board 2 hand ranks ---

    def test_board2_p1_ace_high_flush(self):
        """P1 makes an A-high diamond flush on board 2 (Ad+8d + Jd+9d+7d)."""
        result = HandEvaluator.evaluate(self.p1_hole, self.board2, self.rules)
        assert result.rank == HandRank.FLUSH
        assert result.tiebreaker[1] == 14  # Ace high

    def test_board2_p2_king_high_flush(self):
        """P2 makes a K-high diamond flush on board 2 (Kd+Qd + Jd+9d+7d)."""
        result = HandEvaluator.evaluate(self.p2_hole, self.board2, self.rules)
        assert result.rank == HandRank.FLUSH
        assert result.tiebreaker[1] == 13  # King high

    def test_board2_p3_three_of_a_kind(self):
        """P3 makes three Tens on board 2 (Th+6x + Tc+Ts+Jd = T T T 6 J)."""
        result = HandEvaluator.evaluate(self.p3_hole, self.board2, self.rules)
        assert result.rank == HandRank.THREE_OF_A_KIND

    def test_board2_p1_beats_p2(self):
        """P1 A-high flush beats P2 K-high flush on board 2."""
        r1 = HandEvaluator.evaluate(self.p1_hole, self.board2, self.rules)
        r2 = HandEvaluator.evaluate(self.p2_hole, self.board2, self.rules)
        assert HandEvaluator.compare(r1, r2) > 0

    def test_board2_p2_beats_p3(self):
        """P2 K-high flush beats P3's three-of-a-kind on board 2 (flush > trips in shortdeck)."""
        r2 = HandEvaluator.evaluate(self.p2_hole, self.board2, self.rules)
        r3 = HandEvaluator.evaluate(self.p3_hole, self.board2, self.rules)
        assert HandEvaluator.compare(r2, r3) > 0

    def test_board2_p1_sole_winner(self):
        """P1 wins board 2 outright with the A-high diamond flush."""
        r1 = HandEvaluator.evaluate(self.p1_hole, self.board2, self.rules)
        r2 = HandEvaluator.evaluate(self.p2_hole, self.board2, self.rules)
        r3 = HandEvaluator.evaluate(self.p3_hole, self.board2, self.rules)
        winners = HandEvaluator.find_winners({"p1": r1, "p2": r2, "p3": r3})
        assert winners == ["p1"]

    # --- Side-pot structure ---

    def test_grand_pot_total(self):
        """Total chips in play equal 2600."""
        assert self.p1_total_in + self.p2_total_in + self.p3_total_in == self.grand_pot

    def test_main_pot_amount(self):
        """Main pot (capped at P1's 600) = 1800 chips; all three players eligible."""
        cap = self.p1_total_in  # 600 — the all-in player caps the main pot
        main_pot = cap * 3       # three players each put in 600 toward the main pot
        assert main_pot == 1800

    def test_side_pot_amount(self):
        """Side pot = 800 chips; only P2 and P3 eligible."""
        cap = self.p1_total_in
        side_pot = (self.p2_total_in - cap) + (self.p3_total_in - cap)
        assert side_pot == 800

    # --- Payout distribution ---

    def test_p1_payout(self):
        """
        P1 is eligible for the main pot only.
        Board 1 (P2+P3 win, P1 loses): main 0
        Board 2 (P1 wins):             main 1800/2 = 900
        P1 total = 900
        """
        main_pot = 1800
        p1_board1 = 0                  # P1 loses board 1
        p1_board2 = main_pot // 2      # 900 — P1 wins board 2 main pot share
        assert p1_board1 + p1_board2 == 900

    def test_p2_payout(self):
        """
        P2 eligible for main pot + side pot.
        Board 1 (P2+P3 tie): main 1800/2/2=450, side 800/2/2=200 → 650
        Board 2 (P1 wins main; P2 wins side): main 0, side 800/2=400 → 400
        P2 total = 650 + 400 = 1050
        """
        main_pot = 1800
        side_pot = 800
        p2_board1 = main_pot // 2 // 2 + side_pot // 2 // 2  # 450 + 200 = 650
        p2_board2 = side_pot // 2                             # 400 (P2 beats P3 in side pot)
        assert p2_board1 + p2_board2 == 1050

    def test_p3_payout(self):
        """
        P3 eligible for main pot + side pot.
        Board 1 (P2+P3 tie): main 1800/2/2=450, side 800/2/2=200 → 650
        Board 2 (P1 wins main; P2 wins side): main 0, side 0
        P3 total = 650
        """
        main_pot = 1800
        side_pot = 800
        p3_board1 = main_pot // 2 // 2 + side_pot // 2 // 2  # 450 + 200 = 650
        p3_board2 = 0
        assert p3_board1 + p3_board2 == 650

    def test_payouts_sum_to_grand_pot(self):
        """Sanity check: all payouts sum to the grand pot of 2600."""
        p1_payout = 900
        p2_payout = 1050
        p3_payout = 650
        assert p1_payout + p2_payout + p3_payout == self.grand_pot
