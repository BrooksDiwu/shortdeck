import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.game.table_rules import TableRules


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture
def redis_client() -> MagicMock:
    """Mock Redis client for unit tests."""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.rpush = AsyncMock(return_value=1)
    mock.ltrim = AsyncMock(return_value=True)
    mock.lrange = AsyncMock(return_value=[])
    mock.publish = AsyncMock(return_value=1)
    mock.hset = AsyncMock(return_value=1)
    mock.hget = AsyncMock(return_value=None)
    mock.hgetall = AsyncMock(return_value={})
    mock.eval = AsyncMock(return_value=1)
    return mock


@pytest.fixture
def sample_table_rules() -> TableRules:
    """Standard Texas Hold'em table rules fixture."""
    return TableRules(
        variant="holdem",
        betting="no_limit",
        small_blind=50,
        big_blind=100,
        denomination="chips",
        hole_cards_count=2,
        extra_hole_card=False,
        must_use_exactly_two_hole_cards=False,
        extra_flop=False,
        street_modifiers={},
        max_players=9,
        allow_rebuy=True,
    )


@pytest.fixture
def sample_shortdeck_rules() -> TableRules:
    """Shortdeck Hold'em table rules fixture."""
    return TableRules(
        variant="shortdeck",
        betting="no_limit",
        small_blind=50,
        big_blind=100,
        denomination="chips",
        hole_cards_count=2,
        extra_hole_card=False,
        must_use_exactly_two_hole_cards=False,
        extra_flop=False,
        street_modifiers={},
        max_players=6,
        allow_rebuy=True,
    )
