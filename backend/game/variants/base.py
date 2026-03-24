from abc import ABC, abstractmethod
from ..deck import Deck
from ..hand_evaluator import HandResult, HandRank
from ..card import Card
from ..table_rules import StreetConfig


class BaseVariant(ABC):
    @abstractmethod
    def build_deck(self) -> Deck: ...

    @abstractmethod
    def evaluate_hand(self, hole_cards: list[Card], community_cards: list[Card]) -> HandResult: ...

    @abstractmethod
    def get_hand_rankings(self) -> list[HandRank]: ...

    @abstractmethod
    def streets(self) -> list[StreetConfig]: ...
