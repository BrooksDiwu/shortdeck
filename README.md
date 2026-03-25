# Shortdeck Holdem — Full Stack Poker App

A real-time multiplayer poker webapp supporting Texas Hold'em and Shortdeck Hold'em, with customizable game rules, WebSocket-driven gameplay, and a React/Vite frontend.

---

## Stack Overview

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| Real-time | WebSockets (FastAPI native) |
| Active game state | Redis (persistent, append-only log + snapshot) |
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
    status: Literal["active", "folded", "all_in", "sitting_out", "disconnected"]
    current_bet: int                  # amount bet in current street
    is_admin: bool
    joined_at: datetime               # used for admin transfer order
    disconnect_at: datetime | None    # set on disconnect, cleared on reconnect
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
    action_seq: int                   # monotonically increasing, incremented on every state mutation
    pending_vote: ModeVote | None
```

### Admin Transfer Rules
- Admin is the table creator by default
- If admin disconnects, rights transfer immediately to `player_join_order[1]` (next oldest connected player)
- This transfer happens even mid-hand — the new admin can use admin rights starting next hand
- Admin can force a game mode change without a vote (takes effect next hand)
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

### Side Pot Construction Algorithm

This is one of the most bug-prone areas. The invariant-driven algorithm:

1. Collect each player's total contribution for the hand as `(session_id, total_in)` pairs
2. Sort by `total_in` ascending
3. Iterate in sorted order. For each player at index `i`:
   - `cap = total_in[i]`
   - `pot_amount = sum(min(p.total_in, cap) for all players) - already_allocated`
   - `eligible = {players whose total_in >= cap}`
   - Append `SidePot(amount=pot_amount, eligible_players=eligible)`
   - `already_allocated += pot_amount`
4. Any remaining unclaimed chips (from a player who folded after putting in more than any all-in) go to the main pot eligible set

**Odd chip rules:**
- Odd chips always go to the first active player left of the dealer
- On a split pot with two boards (extra_flop), each board is evaluated independently:
  - Board 1 winners split half the pot; Board 2 winners split the other half
  - If pot is odd, the extra chip goes to Board 1 winner(s)
  - If a board itself splits (tied hands), odd chip within that half goes to first left of dealer

**All-in on different streets:**
- `total_in` accumulates across all streets — side pots are only rebuilt at the end of each betting round, not per-action
- A player who goes all-in on the flop and another on the turn generate separate side pot levels

**Tied hands across side pots:**
- Each `SidePot` is resolved independently
- A player can win a side pot and lose the main pot (or vice versa)
- `find_winners` is called once per pot, not once per hand

### Test cases required (minimum)
- Single all-in below current bet
- Two all-ins at different stack sizes
- All players all-in
- Fold after contributing more than any all-in player
- Split pot (tie) with odd chip
- Dual-board split with odd chip
- All-in on different streets

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
1. `start_hand()` — shuffle deck, deal hole cards (count from `rules.hole_cards_count + extra_hole_card`), post blinds, increment `hand_number`
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
- Triggered between hands only (checked in `end_hand()`)
- `TableRules` is swapped atomically in Redis under the table lock
- Player stacks, hand number, and seat assignments carry over
- A fresh deck is built using the new variant's `build_deck()`
- Admin force-change bypasses vote; voted change applies the same way

### Vote Resolution
- Vote expires if not resolved before `start_hand()` is called
- If vote passes before `start_hand()`, rules are swapped for the next hand
- Ties (equal votes for/against) = vote fails

---

## Section 7 — Concurrency and State Integrity

**Files:** `backend/services/table_service.py`, `backend/websocket/router.py`

Every mutation to table state must be serialized per table to prevent race conditions (e.g. two players acting simultaneously, reconnect racing with a broadcast).

### Distributed Lock (per table)

Uses Redis `SET NX PX` (set-if-not-exists with TTL) as a distributed lock:

```
Lock key:  table:{table_id}:lock
TTL:       5000ms (auto-release if process crashes)
```

Every state mutation follows this pattern:
1. Acquire lock (`SET table:{id}:lock {token} NX PX 5000`)
2. Read current state from `table:{id}:state`
3. Apply action, validate, mutate
4. Increment `action_seq`
5. Append event to `table:{id}:log`
6. Write new state snapshot to `table:{id}:state`
7. Publish to `table_events:{id}` Pub/Sub channel
8. Release lock (delete key only if token matches — Lua script)

If lock acquisition fails (another action in progress), return HTTP 409 / WS error and ask client to retry after a short backoff.

### Redis Key Structure (per table)

| Key | Type | Contents |
|---|---|---|
| `table:{id}:state` | String (JSON) | Full serialized `Table` snapshot |
| `table:{id}:log` | List | Append-only action events (JSON), newest at tail |
| `table:{id}:lock` | String | Lock token, TTL 5s |
| `session:{id}` | String (JSON) | Serialized `Player` |
| `table_events:{id}` | Pub/Sub channel | Broadcast events to all WS connections |

### Event Log Entry Format

```json
{
  "seq": 42,
  "hand": 7,
  "type": "action",
  "session_id": "abc123",
  "street": "flop",
  "action": "raise",
  "amount": 150,
  "timestamp": "2025-01-01T00:00:00Z"
}
```

All broadcast messages include `seq` and `hand` fields. Clients track the last `seq` seen and detect gaps on reconnect.

---

## Section 8 — WebSocket Layer

**Files:** `backend/websocket/manager.py`, `backend/websocket/router.py`

Handles all real-time communication between clients and the server.

### Authentication

WebSocket connections are authenticated at handshake time:
- Client passes a signed JWT as a query parameter: `WS /ws/table/{table_id}?token=<jwt>`
- JWT payload contains `session_id`, `name`, issued-at, expiry (short-lived, e.g. 1h)
- JWT is signed with `SECRET_KEY` from config using HS256
- Server validates token before accepting the WebSocket upgrade — rejects with 401 if invalid/expired
- Seat ownership is validated server-side on every action: the `session_id` in the token must match the seat being acted on
- Clients refresh tokens via `POST /sessions/refresh` before expiry; existing WS connection remains open

### `websocket/manager.py` — `ConnectionManager`
- `connect(table_id, session_id, websocket)`
- `disconnect(table_id, session_id)`
- `broadcast(table_id, message)` — sends to all players at a table via Redis Pub/Sub
- `send_personal(session_id, message)` — private messages (e.g. hole cards)

### `websocket/router.py`
- Route: `WS /ws/table/{table_id}?token=<jwt>`
- On connect: validate JWT, add to manager, send full state snapshot + last `seq`
- Message dispatch: route incoming messages to engine under table lock
- On disconnect: start grace window timer, trigger admin transfer if needed

### Message Format (JSON)

All server → client messages include `seq` (current sequence number) and `hand` (current hand number).

```json
// Client → Server (game action)
{ "type": "action", "action": "raise", "amount": 100 }

// Client → Server (vote)
{ "type": "vote", "vote": "for" }

// Client → Server (request replay after gap detected)
{ "type": "replay_request", "from_seq": 38 }

// Server → Client (incremental event — sent on every state change)
{
  "type": "event",
  "seq": 42,
  "hand": 7,
  "event": "action",
  "session_id": "abc123",
  "action": "raise",
  "amount": 150,
  "state_patch": { "pot": 450, "current_action_seat": 3 }
}

// Server → Client (full state snapshot — sent on connect/reconnect or replay)
{
  "type": "state_snapshot",
  "seq": 42,
  "hand": 7,
  "phase": "flop",
  "board": { "primary": ["Ah", "Kd", "2c"], "secondary": [] },
  "pot": 300,
  "side_pots": [],
  "players": [...],
  "current_action_seat": 2,
  "rules": { ... }
}

// Server → Client (private — hole cards only, never broadcast)
{ "type": "deal", "seq": 12, "hand": 7, "hole_cards": ["As", "Kh"] }

// Server → Client (error)
{ "type": "error", "code": "NOT_YOUR_TURN", "message": "..." }
```

### Reconnect Protocol
1. Client reconnects with valid JWT
2. Server sends full `state_snapshot` with current `seq`
3. Client compares received `seq` to last known `seq`
4. If gap exists, client sends `replay_request` with `from_seq`
5. Server replays events from `table:{id}:log` starting at that seq
6. Client replays events to reconstruct missed state changes

### Notes
- Hole cards are always sent via `send_personal`, never broadcast
- All monetary values sent as integers (chips or cents depending on denomination)
- `state_patch` in incremental events contains only changed fields — clients merge onto local state

---

## Section 9 — REST API and Auth

**Files:** `backend/api/tables.py`, `backend/api/sessions.py`

Handles pre-game setup. All in-game actions go over WebSocket.

### Auth Model

- `POST /sessions` returns a signed JWT (not a raw `session_id`)
- JWT is used for both REST calls (Bearer header) and WS connection (query param)
- All REST endpoints that mutate state require the JWT in `Authorization: Bearer <token>`
- CSRF is not a concern for REST because we use Bearer tokens (not cookies)
- Token expiry: 1 hour; refresh via `POST /sessions/refresh` (returns a new token, same `session_id`)

### `api/sessions.py`
- `POST /sessions` — create a named session, returns `{ token, session_id, expires_at }`
- `POST /sessions/refresh` — exchange a valid (non-expired) token for a new one
- `GET /sessions/me` — return current session info (requires valid token)

### `api/tables.py`
- `POST /tables` — create a new table with `TableRules`; creator becomes admin
- `GET /tables` — list open tables (no auth required)
- `GET /tables/{table_id}` — get table metadata (no auth required)
- `POST /tables/{table_id}/join` — join a table; requires valid token
- `POST /tables/{table_id}/rebuy` — submit a rebuy request; requires token; processed between hands

### Notes
- All seat and admin actions validate that the token's `session_id` matches the claimed seat
- Joining a table that is mid-hand puts the player in `sitting_out` status until the next hand

---

## Section 10 — Disconnect and Reconnect Handling

**Files:** `backend/websocket/router.py`, `backend/game/engine.py`, `backend/services/table_service.py`

Disconnect behavior must be fully specified — these are core product rules, not edge cases.

### Disconnect During Your Turn
- Player is marked `disconnected` immediately
- A **30-second grace timer** starts (stored as `disconnect_at` on the `Player`)
- If the player reconnects within 30 seconds: timer is cleared, their turn resumes normally
- If the timer expires:
  - If **check is a legal action**: auto-check (preserves stack, avoids forced fold)
  - Otherwise: auto-fold
- The auto-action is emitted as a normal event with `session_id` of the player and a `"auto"` flag

### Disconnect When Not Your Turn
- Player is marked `disconnected`; game continues unaffected
- Grace window still applies — if they reconnect before their next turn, they play normally
- If they do not reconnect before it is their turn again, the 30-second timer starts at that point

### Blind Posting After Reconnect
- If a player missed posting a blind while disconnected, they post it automatically on reconnect before being dealt in
- Alternatively they can choose to sit out for the hand

### Admin Disconnect
- Admin rights transfer **immediately** on disconnect (not after the grace window)
- Transfer goes to the next player in `player_join_order` who is currently connected
- If the admin reconnects, they do **not** automatically get admin rights back — the new admin retains them unless they voluntarily transfer

### All Players Disconnected
- Game is paused (no auto-actions, timers frozen) while zero players are connected
- If no players reconnect within **10 minutes**, the table is marked `abandoned`:
  - State is preserved in Redis for another 24h for potential debugging
  - Hand history up to that point is flushed to Postgres
  - Table no longer appears in the lobby

### Table Abandonment Cleanup
- Background task (scheduled via `asyncio` on startup) polls for tables with `abandoned` status older than 24h and deletes their Redis keys

---

## Section 11 — Persistence

**Files:** `backend/models/db.py`, `backend/models/schemas.py`, `backend/services/table_service.py`, `backend/services/session_service.py`

Two-tier persistence: Redis for active game state + event log, PostgreSQL for durable history.

### Redis Structure (per table)

| Key | Type | Purpose |
|---|---|---|
| `table:{id}:state` | String (JSON) | Authoritative snapshot, updated on every mutation |
| `table:{id}:log` | List | Append-only event log; used for reconnect replay |
| `table:{id}:lock` | String | Distributed lock token (TTL 5s) |
| `session:{id}` | String (JSON) | Player session data |
| `table_events:{id}` | Pub/Sub | Live broadcast channel |

- Table state TTL: 24h of inactivity (reset on each write)
- Log retention: last 1000 events per table (trim with `LTRIM` on each append)

### PostgreSQL Schema (`models/db.py`)

```
sessions       — session_id, name, jwt_jti (for revocation), created_at
tables         — table_id, rules_json, created_at, status
hands          — hand_id, table_id, hand_number, rules_snapshot_json, started_at, ended_at
actions        — action_id, hand_id, session_id, street, action_type, amount, seq, timestamp
hand_results   — hand_id, session_id, hole_cards_json, best_hand, board, amount_won
```

### `services/table_service.py`
- `create_table(rules) -> Table`
- `get_table(table_id) -> Table` — reads from Redis
- `save_table(table)` — writes snapshot to `table:{id}:state`
- `append_event(table_id, event)` — appends to `table:{id}:log`, trims to 1000
- `persist_hand(hand_id, actions, results)` — writes to Postgres after hand ends
- `acquire_lock(table_id) -> context manager` — distributed lock acquire/release

### `services/session_service.py`
- `create_session(name) -> (Player, token)`
- `get_session(session_id) -> Player`
- `validate_token(token) -> session_id` — raises on invalid/expired

### Notes
- On server restart, active tables are rehydrated from `table:{id}:state` in Redis
- Hand history in Postgres survives Redis expiry
- Rules snapshot stored per-hand so history reflects rules in effect at time of play
- `jwt_jti` allows individual token revocation (e.g. on kick) by storing revoked JTIs in Redis with TTL matching token expiry

---

## Section 12 — App Entry Point and Config

**Files:** `backend/main.py`, `backend/config.py`, `backend/dependencies.py`

### `config.py`
- Reads from environment variables
- `REDIS_URL`, `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`, `JWT_EXPIRY_SECONDS`

### `dependencies.py`
- FastAPI dependency: `get_redis() -> Redis`
- FastAPI dependency: `get_db() -> AsyncSession`
- FastAPI dependency: `get_current_session(token) -> Player` — validates JWT, returns player

### `main.py`
- Creates FastAPI app
- Registers routers: `api/tables`, `api/sessions`, `websocket/router`
- Startup event: connect Redis, run DB migrations, start abandonment cleanup background task
- CORS config for local dev and production domains

---

## Section 13 — Frontend

> **Full frontend plan:** See [FRONTEND_README.md](FRONTEND_README.md) for the complete frontend design, component breakdown, animation strategy, and build order.

**Folder:** `frontend/`
**Stack:** React + Vite, Zustand, Tailwind CSS v4, Framer Motion + GSAP, React Router v6

Separate Vite + React app. Communicates with the backend via:
- REST (session creation, table creation/listing/joining)
- WebSocket (all in-game real-time events)

### Pages
- `/` — lobby: list open tables (sorted by player count), create table with full `TableRules` form, name entry
- `/table/:id` — game table: oval felt layout, seats around perimeter, community cards + pot in center, action controls, vote/pause banner

### Client-side event handling
- Maintain local `seq` counter (Zustand)
- On each received event: if `event.seq != local_seq + 1`, send `replay_request`
- Apply `state_patch` from incremental events onto local state
- On reconnect: receive full snapshot, reset local state, check for seq gap

### Notes
- Mobile-first design — oval table scales for desktop
- JWT stored in memory only (never localStorage); refreshed on tab focus if near expiry
- All monetary display formatting ($ vs chips) handled client-side based on `denomination`
- Card assets are `.svg` files in `frontend/src/assets/cards/` — fully replaceable
- **Framer Motion** handles card/UI animations; **GSAP** handles chip movement and pot-to-winner animations

---

## Section 14 — Backend Changes Required for Frontend

The following backend additions are needed to support the frontend design. See [FRONTEND_README.md § 13.13](FRONTEND_README.md#section-1313--new-backend-requirements) for full payload specs.

### New `TableRules` Fields
- `timer_enabled: bool` — per-turn timer on/off (set at table creation)
- `timer_seconds: int` — timer duration in seconds

### New `Table` State Fields
- `spectators: list[str]` — session_ids of connected non-seated players
- `pending_sit_requests: list[{ session_id, seat, chips }]` — awaiting host approval
- `is_paused: bool` — game is paused before next hand
- `pause_requested_by: str | None` — session_id of player who requested pause

### New `Player` State Fields
- `is_revealed: list[bool]` — per hole card reveal status, e.g. `[False, False]`

### New WebSocket Messages (client → server)
- `propose_rule_change` — any player proposes a rule change (triggers auto-pause)
- `force_rule_change` — admin only; applies rule change without vote
- `pause_request` / `unpause_request` — any player pauses/unpauses before next hand
- `reveal_card { card_index }` — player reveals one hole card to all
- `rabbit_hunt_request` — winner requests remaining community cards dealt as ghost cards
- `sit_down_request { seat, chips }` — player requests a seat with starting stack
- `approve_sit_down / reject_sit_down { session_id }` — host responds to sit request
- `stand_up` — player vacates their seat (between hands only)
- `host_stand_up / host_remove_player { session_id }` — host manages seated players

### New WebSocket Messages (server → client)
- `sit_down_request` broadcast to host, `sit_down_approved / sit_down_rejected` to player
- `player_stood_up`, `player_removed` — seat state updates
- `card_revealed { session_id, card_index, card }` — broadcast hole card reveal
- `rabbit_hunt { cards }` — ghost community cards (winner only)
- `game_paused`, `game_unpaused` — pause state changes
- `vote_update { votes_for, votes_against, total_eligible }` — live vote tally
- `vote_resolved { passed, new_rules? }` — vote outcome

### Vote & Pause Logic Changes
- Any player (not just admin) can propose a rule change or request pause
- Admin retains ability to force a rule change without a vote
- Vote ends automatically when simple majority is reached (no need to wait for all votes)
- Ties = vote fails (unchanged from current spec)
- Game unpauses automatically on vote resolution: new rules if passed, current rules if failed

---

## Build Order

Each section can be built and tested independently in this order:

| Step | Section | Testable via |
|---|---|---|
| 1 | Card Primitives | Unit tests |
| 2 | Hand Evaluation | Unit tests with known hands |
| 3 | Game Rules + Variants | Unit tests |
| 4 | Player + Table State | Serialization tests |
| 5 | Betting Logic | Unit tests — see required test cases in Section 5 |
| 6 | Game Engine | Integration tests (full hand sim) |
| 7 | Concurrency + State Integrity | Integration tests with concurrent actions |
| 8 | WebSocket Layer | Local WS client with JWT |
| 9 | REST API + Auth | curl / Postman |
| 10 | Disconnect Handling | Simulated disconnect tests |
| 11 | Persistence | Local Redis + Postgres |
| 12 | App Entry Point | `uvicorn main:app` |
| 13 | Frontend | Vite dev server |

---

## Local Development Setup (TODO)

- Python 3.11+
- Redis running locally (`redis-server`)
- PostgreSQL running locally
- `pip install fastapi uvicorn redis asyncpg sqlalchemy pydantic python-jose`
- `uvicorn backend.main:app --reload`

## Production (AWS)

- ECS Fargate — stateless FastAPI containers (scale horizontally; shared state in Redis means any container handles any request)
- ElastiCache — Redis (shared state, event log, pub/sub, distributed locks across all containers)
- RDS — PostgreSQL
- ALB — Application Load Balancer with WebSocket support (`idle_timeout` set high, e.g. 3600s)
- CloudFront — serve frontend static build
