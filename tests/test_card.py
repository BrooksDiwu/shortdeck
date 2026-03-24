import pytest
from backend.game.card import Card, Rank, Suit
from backend.game.deck import Deck


class TestCard:
    def test_str_ace_of_spades(self):
        card = Card(rank=Rank.ACE, suit=Suit.SPADES)
        assert str(card) == "As"

    def test_str_ten_of_diamonds(self):
        card = Card(rank=Rank.TEN, suit=Suit.DIAMONDS)
        assert str(card) == "Td"

    def test_str_king_of_hearts(self):
        card = Card(rank=Rank.KING, suit=Suit.HEARTS)
        assert str(card) == "Kh"

    def test_str_two_of_clubs(self):
        card = Card(rank=Rank.TWO, suit=Suit.CLUBS)
        assert str(card) == "2c"

    def test_str_jack_of_hearts(self):
        card = Card(rank=Rank.JACK, suit=Suit.HEARTS)
        assert str(card) == "Jh"

    def test_str_queen_of_clubs(self):
        card = Card(rank=Rank.QUEEN, suit=Suit.CLUBS)
        assert str(card) == "Qc"

    def test_card_equality(self):
        c1 = Card(Rank.ACE, Suit.SPADES)
        c2 = Card(Rank.ACE, Suit.SPADES)
        assert c1 == c2

    def test_card_inequality(self):
        c1 = Card(Rank.ACE, Suit.SPADES)
        c2 = Card(Rank.KING, Suit.SPADES)
        assert c1 != c2

    def test_card_hashable(self):
        c1 = Card(Rank.ACE, Suit.SPADES)
        c2 = Card(Rank.KING, Suit.HEARTS)
        card_set = {c1, c2}
        assert len(card_set) == 2

    def test_card_to_dict(self):
        card = Card(Rank.ACE, Suit.SPADES)
        d = card.to_dict()
        assert d == {"rank": 14, "suit": "s"}

    def test_card_from_dict(self):
        card = Card.from_dict({"rank": 14, "suit": "s"})
        assert card.rank == Rank.ACE
        assert card.suit == Suit.SPADES

    def test_card_roundtrip(self):
        original = Card(Rank.QUEEN, Suit.DIAMONDS)
        restored = Card.from_dict(original.to_dict())
        assert original == restored


class TestDeck:
    def test_holdem_deck_has_52_cards(self):
        deck = Deck.build("holdem")
        assert deck.remaining == 52

    def test_shortdeck_has_36_cards(self):
        deck = Deck.build("shortdeck")
        assert deck.remaining == 36

    def test_shortdeck_excludes_twos(self):
        deck = Deck.build("shortdeck")
        cards = deck.to_list()
        assert not any(c.rank == Rank.TWO for c in cards)

    def test_shortdeck_excludes_threes(self):
        deck = Deck.build("shortdeck")
        cards = deck.to_list()
        assert not any(c.rank == Rank.THREE for c in cards)

    def test_shortdeck_excludes_fours(self):
        deck = Deck.build("shortdeck")
        cards = deck.to_list()
        assert not any(c.rank == Rank.FOUR for c in cards)

    def test_shortdeck_excludes_fives(self):
        deck = Deck.build("shortdeck")
        cards = deck.to_list()
        assert not any(c.rank == Rank.FIVE for c in cards)

    def test_shortdeck_includes_sixes(self):
        deck = Deck.build("shortdeck")
        cards = deck.to_list()
        sixes = [c for c in cards if c.rank == Rank.SIX]
        assert len(sixes) == 4  # one per suit

    def test_holdem_has_all_ranks(self):
        deck = Deck.build("holdem")
        cards = deck.to_list()
        for rank in Rank:
            assert any(c.rank == rank for c in cards)

    def test_shuffle_changes_order(self):
        deck1 = Deck.build("holdem")
        deck2 = Deck.build("holdem")
        deck2.shuffle()
        # Very unlikely to be the same after shuffle (1/52! chance)
        assert deck1.to_list() != deck2.to_list()

    def test_deal_returns_correct_count(self):
        deck = Deck.build("holdem")
        cards = deck.deal(5)
        assert len(cards) == 5

    def test_deal_reduces_remaining(self):
        deck = Deck.build("holdem")
        deck.deal(7)
        assert deck.remaining == 45

    def test_deal_too_many_raises(self):
        deck = Deck.build("holdem")
        with pytest.raises(ValueError, match="Cannot deal"):
            deck.deal(53)

    def test_deck_cards_are_unique(self):
        deck = Deck.build("holdem")
        cards = deck.to_list()
        assert len(cards) == len(set(cards))

    def test_deck_roundtrip(self):
        deck = Deck.build("holdem")
        deck.shuffle()
        restored = Deck.from_dict(deck.to_dict())
        assert restored.to_list() == deck.to_list()

    def test_shortdeck_all_remaining_ranks_valid(self):
        """All cards in shortdeck should have rank >= 6."""
        deck = Deck.build("shortdeck")
        cards = deck.to_list()
        assert all(c.rank.value >= 6 for c in cards)
