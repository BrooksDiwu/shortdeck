import random
from .card import Card, Rank, Suit


class Deck:
    def __init__(self, cards: list[Card]):
        self._cards = list(cards)

    @classmethod
    def build(cls, variant: str) -> "Deck":
        excluded_ranks: set[Rank] = set()
        if variant == "shortdeck":
            excluded_ranks = {Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE}
        cards = [
            Card(rank, suit)
            for rank in Rank
            for suit in Suit
            if rank not in excluded_ranks
        ]
        return cls(cards)

    def shuffle(self) -> None:
        random.shuffle(self._cards)

    def deal(self, n: int) -> list[Card]:
        if n > len(self._cards):
            raise ValueError(f"Cannot deal {n} cards, only {len(self._cards)} remaining")
        dealt = self._cards[-n:]
        self._cards = self._cards[:-n]
        return dealt

    @property
    def remaining(self) -> int:
        return len(self._cards)

    def to_list(self) -> list[Card]:
        return list(self._cards)

    def to_dict(self) -> dict:
        return {"cards": [c.to_dict() for c in self._cards]}

    @classmethod
    def from_dict(cls, data: dict) -> "Deck":
        cards = [Card.from_dict(c) for c in data["cards"]]
        return cls(cards)
