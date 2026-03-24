from ..deck import Deck
from ..hand_evaluator import HandResult, HandEvaluator, HandRank
from ..card import Card
from ..table_rules import StreetConfig, TableRules
from .base import BaseVariant


class HoldemVariant(BaseVariant):
    """Standard Texas Hold'em — 52-card deck, standard hand rankings."""

    def __init__(self) -> None:
        self._rules = TableRules(
            variant="holdem",
            betting="no_limit",
            small_blind=1,
            big_blind=2,
        )

    def build_deck(self) -> Deck:
        return Deck.build("holdem")

    def evaluate_hand(self, hole_cards: list[Card], community_cards: list[Card]) -> HandResult:
        return HandEvaluator.evaluate(hole_cards, community_cards, self._rules)

    def get_hand_rankings(self) -> list[HandRank]:
        """Return hand ranks from best to worst (standard holdem order)."""
        return [
            HandRank.ROYAL_FLUSH,
            HandRank.STRAIGHT_FLUSH,
            HandRank.FOUR_OF_A_KIND,
            HandRank.FULL_HOUSE,
            HandRank.FLUSH,
            HandRank.STRAIGHT,
            HandRank.THREE_OF_A_KIND,
            HandRank.TWO_PAIR,
            HandRank.ONE_PAIR,
            HandRank.HIGH_CARD,
        ]

    def streets(self) -> list[StreetConfig]:
        return [
            StreetConfig(name="preflop", base_cards=0),
            StreetConfig(name="flop", base_cards=3),
            StreetConfig(name="turn", base_cards=1),
            StreetConfig(name="river", base_cards=1),
        ]
