
from enum import IntEnum
from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING

from .card import Card, Rank, Suit

if TYPE_CHECKING:
    from .table_rules import TableRules
# ---------------------------------------------------------------------------
# Hand rank enumerations — two orderings depending on variant
# ---------------------------------------------------------------------------

class HandRank(IntEnum):
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10
# Shortdeck: Flush (6) beats Full House (5) — we remap to a different ordering
# We store a "shortdeck score" that is used only in the tiebreaker list when
# comparing hands in shortdeck mode.  The HandRank enum values stay the same;
# comparison is done via _effective_rank().
_SHORTDECK_ORDER: dict[HandRank, int] = {
    HandRank.HIGH_CARD: 1,
    HandRank.ONE_PAIR: 2,
    HandRank.TWO_PAIR: 3,
    HandRank.THREE_OF_A_KIND: 4,
    HandRank.STRAIGHT: 5,
    HandRank.FULL_HOUSE: 6,
    HandRank.FLUSH: 7,
    HandRank.FOUR_OF_A_KIND: 8,
    HandRank.STRAIGHT_FLUSH: 9,
    HandRank.ROYAL_FLUSH: 10,
}

_HOLDEM_ORDER: dict[HandRank, int] = {h: h.value for h in HandRank}
# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class HandResult:
    rank: HandRank
    tiebreaker: list[int]   # ordered card values for tie-breaking
    best_cards: list[Card]  # the 5 cards making the hand
    variant: str = "holdem"  # "holdem" or "shortdeck"

    def effective_rank(self) -> int:
        if self.variant == "shortdeck":
            return _SHORTDECK_ORDER[self.rank]
        return _HOLDEM_ORDER[self.rank]
# ---------------------------------------------------------------------------
# Core 5-card evaluation helpers
# ---------------------------------------------------------------------------

def _rank_counts(cards: list[Card]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for c in cards:
        counts[c.rank.value] = counts.get(c.rank.value, 0) + 1
    return counts
def _is_flush(cards: list[Card]) -> bool:
    return len({c.suit for c in cards}) == 1
def _straight_high(ranks: list[int]) -> int | None:
    """Return the high card of the straight, or None if not a straight."""
    unique = sorted(set(ranks), reverse=True)
    if len(unique) < 5:
        return None
    # Normal straight
    for i in range(len(unique) - 4):
        window = unique[i:i + 5]
        if window[0] - window[4] == 4:
            return window[0]
    # Ace-low straight: A-2-3-4-5 (holdem) — ace acts as 1
    if 14 in unique:
        # Replace 14 (ace) with 1: remove the ace (first element, highest) and add 1
        without_ace = [r for r in unique if r != 14]
        ace_low = sorted(without_ace + [1], reverse=True)
        for i in range(len(ace_low) - 4):
            window = ace_low[i:i + 5]
            if window[0] - window[4] == 4:
                return window[0]
    return None


def _straight_high_shortdeck(ranks: list[int]) -> int | None:
    """Return the high card of the straight for shortdeck (A-6-7-8-9 valid)."""
    unique = sorted(set(ranks), reverse=True)
    if len(unique) < 5:
        return None
    # Normal straight
    for i in range(len(unique) - 4):
        window = unique[i:i + 5]
        if window[0] - window[4] == 4:
            return window[0]
    # Ace-low shortdeck: A-6-7-8-9 — ace acts as 5 (the card just below 6)
    if 14 in unique:
        # Replace 14 (ace) with 5: remove the ace and add 5
        without_ace = [r for r in unique if r != 14]
        ace_low = sorted(without_ace + [5], reverse=True)
        for i in range(len(ace_low) - 4):
            window = ace_low[i:i + 5]
            if window[0] - window[4] == 4:
                return window[0]
    return None
def _best_straight_cards(cards: list[Card], high: int, shortdeck: bool) -> list[Card]:
    """Return the 5 cards forming the straight with the given high card."""
    # Build a rank->card mapping (prefer highest suit for determinism)
    rank_map: dict[int, Card] = {}
    for c in cards:
        rv = c.rank.value
        if rv not in rank_map or c.suit.value > rank_map[rv].suit.value:
            rank_map[rv] = c

    # Determine the 5 ranks in this straight
    needed_high = high
    target_ranks: list[int] = []

    # Detect ace-low case
    ace_low_holdem = (high == 5 and not shortdeck and 14 in rank_map)
    ace_low_shortdeck = (high == 9 and shortdeck and 14 in rank_map and 6 in rank_map
                         and 7 in rank_map and 8 in rank_map and 9 in rank_map)
    # More general ace-low shortdeck: high=9 and the window is 9,8,7,6,A(as5)
    if shortdeck and 14 in rank_map:
        # Check if this is the A-6-7-8-9 straight (high = 9 in normal ranking)
        ace_as_5_window = [9, 8, 7, 6, 5]
        actual = [rank_map.get(r) or rank_map.get(14 if r == 5 else r) for r in ace_as_5_window]
        if all(actual) and high == 9:
            result = []
            for r in ace_as_5_window:
                if r == 5:
                    result.append(rank_map[14])
                else:
                    result.append(rank_map[r])
            return result

    if not shortdeck and 14 in rank_map and high == 5:
        # Ace-low holdem: A-2-3-4-5
        target_ranks = [5, 4, 3, 2, 14]  # ace plays as 1
        return [rank_map[r] for r in target_ranks if r in rank_map]

    for offset in range(5):
        target_ranks.append(high - offset)
    return [rank_map[r] for r in target_ranks if r in rank_map]
def _evaluate_5(cards: list[Card], shortdeck: bool = False) -> HandResult:
    """Evaluate a 5-card hand and return HandResult."""
    assert len(cards) == 5
    ranks = [c.rank.value for c in cards]
    counts = _rank_counts(cards)
    flush = _is_flush(cards)
    straight_fn = _straight_high_shortdeck if shortdeck else _straight_high
    straight_h = straight_fn(ranks)

    sorted_ranks = sorted(ranks, reverse=True)
    count_items = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)

    variant = "shortdeck" if shortdeck else "holdem"

    # Royal flush
    if flush and straight_h == 14:
        return HandResult(
            rank=HandRank.ROYAL_FLUSH,
            tiebreaker=[HandRank.ROYAL_FLUSH],
            best_cards=sorted(cards, key=lambda c: c.rank.value, reverse=True),
            variant=variant,
        )

    # Straight flush
    if flush and straight_h is not None:
        sf_cards = _best_straight_cards(cards, straight_h, shortdeck)
        return HandResult(
            rank=HandRank.STRAIGHT_FLUSH,
            tiebreaker=[HandRank.STRAIGHT_FLUSH, straight_h],
            best_cards=sf_cards or cards,
            variant=variant,
        )

    # Four of a kind
    if 4 in counts.values():
        quad_rank = next(r for r, c in counts.items() if c == 4)
        kicker = next(r for r, c in counts.items() if c != 4)
        quad_cards = [c for c in cards if c.rank.value == quad_rank]
        kicker_cards = [c for c in cards if c.rank.value == kicker]
        return HandResult(
            rank=HandRank.FOUR_OF_A_KIND,
            tiebreaker=[HandRank.FOUR_OF_A_KIND, quad_rank, kicker],
            best_cards=quad_cards + kicker_cards,
            variant=variant,
        )

    # Full house
    if sorted(counts.values()) == [2, 3]:
        triple_rank = next(r for r, c in counts.items() if c == 3)
        pair_rank = next(r for r, c in counts.items() if c == 2)
        triple_cards = [c for c in cards if c.rank.value == triple_rank]
        pair_cards = [c for c in cards if c.rank.value == pair_rank]
        return HandResult(
            rank=HandRank.FULL_HOUSE,
            tiebreaker=[HandRank.FULL_HOUSE, triple_rank, pair_rank],
            best_cards=triple_cards + pair_cards,
            variant=variant,
        )

    # Flush
    if flush:
        return HandResult(
            rank=HandRank.FLUSH,
            tiebreaker=[HandRank.FLUSH] + sorted_ranks,
            best_cards=sorted(cards, key=lambda c: c.rank.value, reverse=True),
            variant=variant,
        )

    # Straight
    if straight_h is not None:
        straight_cards = _best_straight_cards(cards, straight_h, shortdeck)
        return HandResult(
            rank=HandRank.STRAIGHT,
            tiebreaker=[HandRank.STRAIGHT, straight_h],
            best_cards=straight_cards or cards,
            variant=variant,
        )

    # Three of a kind
    if 3 in counts.values() and 2 not in counts.values():
        triple_rank = next(r for r, c in counts.items() if c == 3)
        kickers = sorted([r for r, c in counts.items() if c != 3], reverse=True)
        triple_cards = [c for c in cards if c.rank.value == triple_rank]
        kicker_cards = sorted(
            [c for c in cards if c.rank.value != triple_rank],
            key=lambda c: c.rank.value, reverse=True,
        )
        return HandResult(
            rank=HandRank.THREE_OF_A_KIND,
            tiebreaker=[HandRank.THREE_OF_A_KIND, triple_rank] + kickers,
            best_cards=triple_cards + kicker_cards,
            variant=variant,
        )

    # Two pair
    pairs = [r for r, c in counts.items() if c == 2]
    if len(pairs) == 2:
        high_pair = max(pairs)
        low_pair = min(pairs)
        kicker = next(r for r, c in counts.items() if c == 1)
        hp_cards = [c for c in cards if c.rank.value == high_pair]
        lp_cards = [c for c in cards if c.rank.value == low_pair]
        k_cards = [c for c in cards if c.rank.value == kicker]
        return HandResult(
            rank=HandRank.TWO_PAIR,
            tiebreaker=[HandRank.TWO_PAIR, high_pair, low_pair, kicker],
            best_cards=hp_cards + lp_cards + k_cards,
            variant=variant,
        )

    # One pair
    if len(pairs) == 1:
        pair_rank = pairs[0]
        kickers = sorted([r for r, c in counts.items() if c != 2], reverse=True)
        pair_cards = [c for c in cards if c.rank.value == pair_rank]
        kicker_cards = sorted(
            [c for c in cards if c.rank.value != pair_rank],
            key=lambda c: c.rank.value, reverse=True,
        )
        return HandResult(
            rank=HandRank.ONE_PAIR,
            tiebreaker=[HandRank.ONE_PAIR, pair_rank] + kickers,
            best_cards=pair_cards + kicker_cards,
            variant=variant,
        )

    # High card
    return HandResult(
        rank=HandRank.HIGH_CARD,
        tiebreaker=[HandRank.HIGH_CARD] + sorted_ranks,
        best_cards=sorted(cards, key=lambda c: c.rank.value, reverse=True),
        variant=variant,
    )
# ---------------------------------------------------------------------------
# Public HandEvaluator
# ---------------------------------------------------------------------------

class HandEvaluator:
    @staticmethod
    def evaluate(
        hole_cards: list[Card],
        community_cards: list[Card],
        rules: "TableRules",
    ) -> HandResult:
        shortdeck = rules.variant == "shortdeck"
        variant = rules.variant

        all_cards = hole_cards + community_cards

        if rules.must_use_exactly_two_hole_cards:
            # PLO mode: must use exactly 2 hole cards and exactly 3 community cards
            best: HandResult | None = None
            for hc in combinations(hole_cards, 2):
                for cc in combinations(community_cards, 3):
                    five = list(hc) + list(cc)
                    result = _evaluate_5(five, shortdeck)
                    result.variant = variant
                    if best is None or HandEvaluator.compare(result, best) > 0:
                        best = result
            if best is None:
                # fallback — shouldn't happen with valid input
                best = _evaluate_5(all_cards[:5], shortdeck)
                best.variant = variant
            return best
        else:
            # Standard mode: best 5 of N cards
            best = None
            for five in combinations(all_cards, 5):
                result = _evaluate_5(list(five), shortdeck)
                result.variant = variant
                if best is None or HandEvaluator.compare(result, best) > 0:
                    best = result
            if best is None:
                best = _evaluate_5(all_cards[:5], shortdeck)
                best.variant = variant
            return best

    @staticmethod
    def compare(result_a: HandResult, result_b: HandResult) -> int:
        """Return -1 if a < b, 0 if a == b, 1 if a > b."""
        rank_a = result_a.effective_rank()
        rank_b = result_b.effective_rank()
        if rank_a != rank_b:
            return 1 if rank_a > rank_b else -1
        # Same hand rank — compare tiebreakers element by element
        for va, vb in zip(result_a.tiebreaker[1:], result_b.tiebreaker[1:]):
            if va != vb:
                return 1 if va > vb else -1
        return 0

    @staticmethod
    def find_winners(player_results: dict[str, HandResult]) -> list[str]:
        """Return list of session_ids with the best hand (handles ties)."""
        if not player_results:
            return []
        best_result: HandResult | None = None
        for result in player_results.values():
            if best_result is None or HandEvaluator.compare(result, best_result) > 0:
                best_result = result
        assert best_result is not None
        return [
            sid for sid, result in player_results.items()
            if HandEvaluator.compare(result, best_result) == 0
        ]
