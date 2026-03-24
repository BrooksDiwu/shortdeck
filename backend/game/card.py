from enum import Enum
from dataclasses import dataclass


class Suit(str, Enum):
    CLUBS = "c"
    DIAMONDS = "d"
    HEARTS = "h"
    SPADES = "s"


class Rank(int, Enum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    def short(self) -> str:
        names = {10: "T", 11: "J", 12: "Q", 13: "K", 14: "A"}
        return names.get(self.value, str(self.value))


@dataclass(frozen=True)
class Card:
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.short()}{self.suit.value}"

    def __repr__(self) -> str:
        return str(self)

    def to_dict(self) -> dict:
        return {"rank": self.rank.value, "suit": self.suit.value}

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        return cls(rank=Rank(data["rank"]), suit=Suit(data["suit"]))
