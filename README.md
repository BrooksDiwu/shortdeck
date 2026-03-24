# Shortdeck Holdem — Full Stack Poker App

A real-time multiplayer poker webapp supporting Texas Hold'em and Shortdeck Hold'em, with customizable game rules, WebSocket-driven gameplay, and a React/Vite frontend.

---

## Stack Overview

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| Real-time | WebSockets (FastAPI native) |
| Active game state | Redis (persistent) |
| Durable storage | PostgreSQL |
| Frontend | React + Vite (separate folder) |
| Infra (prod) | AWS ECS (Fargate) + ElastiCache + RDS |

---

## Repository Structure

```
/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── game/
│   │   ├── card.py
│   │   ├── deck.py
│   │   ├── hand_evaluator.py
│   │   ├── table_rules.py
│   │   ├── player.py
│   │   ├── table.py
│   │   ├── betting.py
│   │   ├── engine.py
│   │   └── variants/
│   │       ├── base.py
│   │       ├── holdem.py
│   │       └── shortdeck.py
│   ├── websocket/
│   │   ├── manager.py
│   │   └── router.py
│   ├── api/
│   │   ├── tables.py
│   │   └── sessions.py
│   ├── models/
│   │   ├── db.py
│   │   └── schemas.py
│   └── services/
│       ├── table_service.py
│       └── session_service.py
└── frontend/                        # TODO — React + Vite
```

---

## Section 1 — Card Primitives

**Files:** `backend/game/card.py`, `backend/game/deck.py`

These are the lowest-level building blocks. Everything else depends on them.

### `game/card.py`
- `Suit` enum: `CLUBS, DIAMONDS, HEARTS, SPADES`
- `Rank` enum: values 2–14 (Ace = 14)
- `Card` dataclass: `rank: Rank`, `suit: Suit`
  - `__str__` for human-readable output (e.g. `Ah`, `Td`)
  - `__eq__` and `__hash__` for set/dict use

### `game/deck.py`
- `Deck` class
  - `build(variant)` class method — returns full 52-card deck (Hold'em) or 36-card deck (Shortdeck, removing 2–5)
  - `shuffle()` — randomizes order
  - `deal(n)` — pops and returns n cards
  - `remaining` — count of cards left

### Notes
- Shortdeck removes all cards ranked 2, 3, 4, 5 (20 cards removed, 36 remain)
- Deck is stateless between hands — a fresh deck is built at the start of each hand

---

## Section 2 — Hand Evaluation

**Files:** `backend/game/hand_evaluator.py`

Evaluates and ranks poker hands. Must support two separate ranking systems.

### Standard Hold'em Rankings (high to low)
1. Royal Flush
2. Straight Flush
3. Four of a Kind
4. Full House
5. Flush
6. Straight
7. Three of a Kind
8. Two Pair
9. One Pair
10. High Card

### Shortdeck Rankings (high to low)
Flushes are harder to make with 36 cards, so ranking order shifts:
1. Royal Flush
2. Straight Flush
3. Four of a Kind
4. Flush
5. Full House
6. Straight
7. Three of a Kind
8. Two Pair
9. One Pair
10. High Card

### `HandResult` dataclass
- `rank: HandRank` (enum)
- `tiebreaker: list[int]` — ordered card values for breaking ties within the same hand rank
- `best_cards: list[Card]` — the 5 cards making the hand

### `HandEvaluator` class
- `evaluate(hole_cards, community_cards, rules: TableRules) -> HandResult`
  - Selects ranking system based on `rules.variant`
  - If `rules.must_use_exactly_two_hole_cards` (PLO mode): iterates all `C(hole_cards, 2)` × `C(community_cards, 3)` combinations and returns best
  - Standard mode: best 5 of 7
- `compare(result_a, result_b) -> int` — returns -1, 0, 1
- `find_winners(player_results: dict[str, HandResult]) -> list[str]` — handles ties

### Notes
- Ace plays low in straights (A-6-7-8-9 is valid in Shortdeck)
- Evaluation is called at showdown and also used for side pot winner resolution

---

## Section 3 — Game Rules and Variants

**Files:** `backend/game/table_rules.py`, `backend/game/variants/base.py`, `backend/game/variants/holdem.py`, `backend/game/variants/shortdeck.py`

Defines the full rule set for a table. The engine reads `TableRules` at runtime — no hardcoded logic in the engine itself.

### `game/table_rules.py`

```python
@dataclass
class StreetConfig:
    name: str           # "flop", "turn", "river"
    base_cards: int     # 3, 1, 1
    card_modifier: int  # -1, 0, or +1

@dataclass
class TableRules:
    # Core variant
    variant: Literal["holdem", "shortdeck"]
    betting: Literal["no_limit", "pot_limit"]

    # Blinds and stacks
    small_blind: int
    big_blind: int
    denomination: Literal["chips", "usd"]

    # Hole cards
    hole_cards_count: int = 2            # 2 = holdem, 4 = PLO
    extra_hole_card: bool = False        # deals +1 to all players
    must_use_exactly_two_hole_cards: bool = False  # PLO evaluation rule

    # Community cards
    extra_flop: bool = False             # deal a second flop simultaneously
    street_modifiers: dict[str, int] = field(default_factory=dict)
    # e.g. {"turn": 1, "river": -1}

    # Table config
    max_players: int = 9                 # configurable, up to 9
    allow_rebuy: bool = True
```

### `game/variants/base.py`
Abstract base class all variants implement:
- `build_deck() -> Deck`
- `evaluate_hand(hole_cards, community_cards) -> HandResult`
- `get_hand_rankings() -> list[HandRank]`
- `streets() -> list[StreetConfig]` — canonical street order for this variant

### `game/variants/holdem.py`
- Standard 52-card deck
- Standard hand rankings
- Streets: preflop → flop (3) → turn (1) → river (1)

### `game/variants/shortdeck.py`
- 36-card deck (2–5 removed)
- Modified hand rankings (flush beats full house)
- Ace plays low in A-6-7-8-9 straights
- Streets: same structure as holdem

### Notes
- When transitioning game modes mid-game, `TableRules` is replaced but player stack sizes carry over
- Street modifiers and extra hole card stack on top of the base variant — they are not variant-specific

---

## Section 4 — Player and Table State

**Files:** `backend/game/player.py`, `backend/game/table.py`

Pure state dataclasses with no game logic. Serializable to/from Redis (JSON).

### `game/player.py`

```python
@dataclass
class Player:
    session_id: str
    name: str
    stack: int                        # current chip count
    hole_cards: list[Card]
    seat: int                         # 0-indexed seat position
    status: Literal["active", "folded", "all_in", "sitting_out"]
    current_bet: int                  # amount bet in current street
    is_admin: bool
    joined_at: datetime               # used for admin transfer order
```

### `game/table.py`

```python
@dataclass
class Board:
    primary: list[Card]               # main board
    secondary: list[Card]             # second board if extra_flop=True

@dataclass
class ModeVote:
    proposed_rules: TableRules
    proposed_by: str                  # session_id
    votes_for: set[str]
    votes_against: set[str]
    expires_at: datetime              # auto-cancel if not resolved before next hand

@dataclass
class Table:
    table_id: str
    players: dict[str, Player]        # keyed by session_id
    player_join_order: list[str]      # session_ids in join order, for admin transfer
    admin_id: str
    rules: TableRules
    board: Board
    pot: int
    side_pots: list[SidePot]
    deck: Deck
    dealer_seat: int
    current_action_seat: int
    phase: Literal["waiting", "preflop", "flop", "turn", "river", "showdown", "between_hands"]
    hand_number: int
    pending_vote: ModeVote | None
```

### Admin Transfer Rules
- Admin is the table creator by default
- If admin disconnects or leaves, rights transfer to `player_join_order[1]` (next oldest player)
- Admin can force a game mode change without a vote
- Admin can also initiate a vote for democratic changes

### Rebuy Rules
- Players can rebuy between hands only (not mid-hand)
- Rebuy amount is configurable per table (up to table max buy-in)
- Stack size persists across game mode transitions

---

## Section 5 — Betting Logic

**Files:** `backend/game/betting.py`

Handles all chip movement, pot construction, and action validation.

### Responsibilities
- Validate actions: `fold`, `check`, `call`, `raise`, `all_in`
- Enforce no-limit vs pot-limit raise sizing
- Build side pots when one or more players are all-in
- Track `current_bet` per player per street
- Reset bets at start of each new street

### `SidePot` dataclass
```python
@dataclass
class SidePot:
    amount: int
    eligible_players: set[str]    # session_ids who can win this pot
```

### Pot-Limit Raise Calculation
- Max raise = current pot size (including the call amount)
- `max_raise = pot + (2 * call_amount)`

### No-Limit Rules
- Min raise = size of the previous raise (or big blind if no raise yet)
- No max raise

### Side Pot Construction
- Triggered when a player goes all-in for less than the current bet
- All pots are resolved independently at showdown

---

## Section 6 — Game Engine

**Files:** `backend/game/engine.py`

The core game loop. Orchestrates all other game modules. Reads `TableRules` to determine behavior — no hardcoded variant logic here.

### `GameEngine` class
```python
class GameEngine:
    def __init__(self, table: Table, rules: TableRules, variant: BaseVariant):
        ...
```

### Hand Lifecycle
1. `start_hand()` — shuffle deck, deal hole cards (count from `rules.hole_cards_count + extra_hole_card`), post blinds
2. `run_streets()` — iterate streets from `variant.streets()`, applying `rules.street_modifiers`
3. Per street:
   - Deal community cards to `board.primary` (and `board.secondary` if `rules.extra_flop`)
   - Run betting round
4. `showdown()` — evaluate hands, resolve side pots, award chips
5. `end_hand()` — rotate dealer, check for pending mode vote resolution, persist hand history

### Street Construction
```python
def build_streets(self) -> list[StreetConfig]:
    streets = self.variant.streets()
    for street in streets:
        modifier = self.rules.street_modifiers.get(street.name, 0)
        street.base_cards += modifier
    if self.rules.extra_flop:
        # inject secondary flop into board
    return streets
```

### Mode Transition (mid-game)
- Triggered between hands only
- `TableRules` is swapped atomically
- Player stacks and hand number carry over
- A fresh deck is built using the new variant
- Admin force-change bypasses vote; voted change applies same way

### Vote Resolution
- Vote expires if not resolved before `start_hand()` is called
- If vote passes before `start_hand()`, rules are swapped for next hand
- Ties (equal votes for/against) = vote fails

---

## Section 7 — WebSocket Layer

**Files:** `backend/websocket/manager.py`, `backend/websocket/router.py`

Handles all real-time communication between clients and the server.

### `websocket/manager.py` — `ConnectionManager`
- `connect(table_id, session_id, websocket)`
- `disconnect(table_id, session_id)`
- `broadcast(table_id, message)` — send to all players at a table
- `send_personal(session_id, message)` — private messages (e.g. hole cards)
- Uses Redis Pub/Sub so broadcasts work across multiple server instances

### `websocket/router.py`
- Route: `WS /ws/table/{table_id}`
- On connect: validate session, add to manager, send current table state
- Message dispatch: route incoming action messages to engine
- On disconnect: mark player as sitting out, trigger admin transfer if needed

### Message Format (JSON)
```json
// Client → Server (action)
{
  "type": "action",
  "action": "raise",
  "amount": 100
}

// Client → Server (vote)
{
  "type": "vote",
  "vote": "for"
}

// Server → Client (game state update)
{
  "type": "state_update",
  "phase": "flop",
  "board": { "primary": ["Ah", "Kd", "2c"], "secondary": [] },
  "pot": 300,
  "players": [...],
  "current_action_seat": 2
}

// Server → Client (private — hole cards)
{
  "type": "deal",
  "hole_cards": ["As", "Kh"]
}
```

### Notes
- Hole cards are always sent via `send_personal`, never broadcast
- All monetary values are sent as integers (chips or cents, depending on denomination)

---

## Section 8 — REST API

**Files:** `backend/api/tables.py`, `backend/api/sessions.py`

Handles pre-game setup. All in-game actions go over WebSocket.

### `api/sessions.py`
- `POST /sessions` — create a named session, returns `session_id`
- `GET /sessions/{session_id}` — validate existing session

### `api/tables.py`
- `POST /tables` — create a new table with `TableRules`, returns `table_id`
- `GET /tables` — list open tables
- `GET /tables/{table_id}` — get table metadata and current state
- `POST /tables/{table_id}/join` — join a table with a `session_id`
- `POST /tables/{table_id}/rebuy` — submit a rebuy request (processed between hands)

---

## Section 9 — Persistence

**Files:** `backend/models/db.py`, `backend/models/schemas.py`, `backend/services/table_service.py`, `backend/services/session_service.py`

Two-tier persistence: Redis for active game state, PostgreSQL for durable history.

### Redis (active state)
- Key: `table:{table_id}` → serialized `Table` JSON
- Key: `session:{session_id}` → serialized `Player` JSON
- Pub/Sub channel: `table_events:{table_id}`
- TTL: tables expire after 24h of inactivity

### PostgreSQL Schema (`models/db.py`)
```
sessions       — session_id, name, created_at
tables         — table_id, rules_json, created_at, status
hands          — hand_id, table_id, hand_number, rules_snapshot_json, started_at, ended_at
actions        — action_id, hand_id, session_id, street, action_type, amount, timestamp
hand_results   — hand_id, session_id, hole_cards, best_hand, amount_won
```

### `services/table_service.py`
- `create_table(rules) -> Table`
- `get_table(table_id) -> Table`
- `save_table(table)` — writes to Redis
- `persist_hand(hand_id, actions, results)` — writes to Postgres

### `services/session_service.py`
- `create_session(name) -> Player`
- `get_session(session_id) -> Player`

### Notes
- On server restart, active tables are rehydrated from Redis
- Hand history in Postgres survives Redis expiry
- Rules snapshot is stored per-hand so history reflects the rules in effect at the time

---

## Section 10 — App Entry Point and Config

**Files:** `backend/main.py`, `backend/config.py`, `backend/dependencies.py`

### `config.py`
- Reads from environment variables
- `REDIS_URL`, `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`

### `dependencies.py`
- FastAPI dependency: `get_redis() -> Redis`
- FastAPI dependency: `get_db() -> AsyncSession`

### `main.py`
- Creates FastAPI app
- Registers routers: `api/tables`, `api/sessions`, `websocket/router`
- Startup event: connect Redis, run DB migrations
- CORS config for local dev and production domains

---

## Section 11 — Frontend (TODO)

**Folder:** `frontend/`

Separate Vite + React app. Communicates with the backend via:
- REST (session creation, table creation/listing/joining)
- WebSocket (all in-game real-time events)

### Planned pages
- `/` — lobby: list open tables, create table, enter name
- `/table/:id` — game table: board, player seats, action buttons, vote UI

### Notes
- Runs on its own dev server (e.g. `localhost:5173`) during local development
- In production, served as a static build via CloudFront or similar
- All monetary display formatting ($ vs chips) handled client-side based on `denomination` from table rules

---

## Build Order

Each section can be built and tested independently in this order:

| Step | Section | Testable via |
|---|---|---|
| 1 | Card Primitives | Unit tests |
| 2 | Hand Evaluation | Unit tests with known hands |
| 3 | Game Rules + Variants | Unit tests |
| 4 | Player + Table State | Serialization tests |
| 5 | Betting Logic | Unit tests |
| 6 | Game Engine | Integration tests (full hand sim) |
| 7 | WebSocket Layer | Local WS client |
| 8 | REST API | curl / Postman |
| 9 | Persistence | Local Redis + Postgres |
| 10 | App Entry Point | `uvicorn main:app` |
| 11 | Frontend | Vite dev server |

---

## Local Development Setup (TODO)

- Python 3.11+
- Redis running locally (`redis-server`)
- PostgreSQL running locally
- `pip install fastapi uvicorn redis asyncpg sqlalchemy pydantic`
- `uvicorn backend.main:app --reload`

## Production (AWS)

- ECS Fargate — stateless FastAPI containers (scale horizontally)
- ElastiCache — Redis (shared state across containers)
- RDS — PostgreSQL
- ALB — Application Load Balancer with WebSocket support enabled
- CloudFront — serve frontend static build
