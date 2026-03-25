# Frontend Plan — Shortdeck Holdem

**Folder:** `frontend/`
**Stack:** React + Vite, Zustand, Tailwind CSS v4, Framer Motion + GSAP, React Router v6

> See [README.md](README.md) for backend architecture and API contracts this frontend depends on.

---

## Tech Stack

| Concern | Library | Why |
|---|---|---|
| Framework | React + Vite | Fast HMR, native ESM |
| State | Zustand | 1.16KB, zero boilerplate, best WebSocket middleware pattern |
| Styling | Tailwind CSS v4 | Native mobile-first, dark mode utilities, zero runtime |
| Animations (UI) | **Framer Motion** | Card deals, reveals, layout transitions, seat animations |
| Animations (chips) | **GSAP + @gsap/react** | Heavy chip movement — 10+ simultaneous tweens moving to winner; use GSAP anywhere Framer Motion drops frames |
| Router | React Router v6 | Well-documented, nested routes, sufficient for 3-page app |
| Cards | SVG deck (replaceable) | All card assets are `.svg` files in `frontend/src/assets/cards/` — drop in a new set to replace |
| Sound | Howler.js | Card deal, chip clink, your-turn notification |

### Animation Rule of Thumb
- **Framer Motion** for: card flip, card deal, card reveal, seat join/leave, modal transitions, vote banner slide-in
- **GSAP** for: chip stacks moving to winner, pot explosion on large wins, simultaneous multi-chip tweens
- Never mix both libraries on the same element

---

## Pages & Routes

```
/                    → Lobby
/table/:id           → Game Table
```

---

## Section 13.1 — Lobby Page (`/`)

### Layout (mobile-first)
- Full-screen dark background (`bg-zinc-950`)
- App name / logo centered at top
- Two-column card grid of open tables (single column on mobile)
- Sticky "Create Table" button at bottom

### Table List Card
Each open table shows:
- Table name
- Game mode (e.g. "NLH", "NL Shortdeck", "PLO", "PLO Shortdeck")
- Blinds (e.g. "10 / 20")
- Player count (e.g. "4 / 9")
- "Join" button

Tables are sorted by player count descending.

### Name Entry
- On clicking "Join" or "Create Table", a bottom sheet modal (mobile) / centered modal (desktop) prompts for a display name
- Name is stored in Zustand session store; `POST /sessions` is called to obtain JWT
- JWT stored in memory only (never localStorage) — refreshed on tab focus if near expiry

### Create Table Form
**Basic fields (always visible):**
- Table name
- Game mode: `No Limit Hold'em` | `No Limit Shortdeck` | `Pot Limit Omaha` | `PLO Shortdeck`
- Small blind / Big blind
- Max players (2–9)

**Advanced fields (hidden behind "Advanced Options" toggle):**
- Denomination: chips / USD
- Hole cards count (override)
- Extra hole card
- Must use exactly two hole cards (PLO evaluation rule)
- Extra flop
- Street modifiers (turn / river card count delta)
- Allow rebuy
- Turn timer on/off (if on: timer duration in seconds)

Host must also enter their display name before the table is created. On submit: `POST /sessions` → `POST /tables` → redirect to `/table/:id`.

---

## Section 13.2 — Game Table Page (`/table/:id`)

### Overall Layout (mobile-first)

```
┌─────────────────────────────┐
│  [Options]       [NLH 10/20]│  ← top bar
│                             │
│   ┌──────────────────────┐  │
│   │   OVAL FELT TABLE    │  │  ← SVG oval, dark green felt
│   │    [pot + board]     │  │
│   │  seats around edge   │  │
│   └──────────────────────┘  │
│                             │
│   [ACTION CONTROLS]         │  ← bottom bar (default position)
│   [LOG/LEDGER]              │
└─────────────────────────────┘
```

On desktop, the oval scales up and seats spread further apart. Action controls remain bottom-right by default.

### Oval Table
- SVG or CSS ellipse with dark green felt texture (`bg-green-900` or custom texture class)
- Dark brown/black rim border
- Community cards and pot displayed in center
- Seats positioned around the perimeter using polar coordinate math

### Seat Positioning
- Local player's seat is always anchored to **bottom center** of the oval
- Other seats are distributed evenly around the remaining perimeter
- Seat count adjusts dynamically to `rules.max_players`
- Empty seats show a dashed border + "SIT" label; clicking an empty seat opens the sit-down flow

---

## Section 13.3 — Player Seat Tile

Each seat around the oval renders a small card/chip showing:

| Element | Visibility |
|---|---|
| Player name | Always |
| Stack size | Always |
| Dealer button (D badge) | When player is dealer |
| SB / BB auto-post indicator | Flashes briefly when blinds are posted; not persistently shown |
| Current bet amount | During betting round, shown below seat tile |
| Hole cards | Face-down backs for opponents; face-up for local player |
| Thinking indicator | Animated pulse ring when it's this player's turn |
| Turn timer | Arc progress ring around seat (only if timer enabled in table rules) |
| Disconnected badge | Shown when player status is `disconnected` |
| Sitting out badge | Shown when player status is `sitting_out` |

**Framer Motion** handles seat appear/disappear transitions and card back dealing animations.

### Hole Card Reveal (local player)
- Cards are face-up for the local player by default
- Player can click a card to reveal it to all players
- Confirmation modal: "Reveal your [card]? This cannot be undone." with Confirm / Cancel
- On confirm: emits a `reveal_card` WS message; card flips face-up for all connected clients
- Player can reveal one or both cards independently

### Rabbit Hunt
- After a hand ends before showdown (everyone folds), a "Rabbit Hunt?" button appears in the center of the table
- Only the last remaining player (winner) sees this button
- On click: server deals the remaining community cards face-up as ghost cards (visually distinct — desaturated / translucent)
- Ghost cards are cleared at the start of the next hand
- Rabbit hunt is a view-only feature; it does not affect hand history or chip counts

---

## Section 13.4 — Action Controls

Two layout modes, toggled via a settings icon:

### Mode A — Bottom Bar (default)
- Fixed bar at bottom of screen
- Buttons: `Fold` | `Check/Call` | `Raise`
- Raise slider / input appears inline when Raise is tapped
- Pot-limit max is pre-calculated and shown as a quick-select chip

### Mode B — Overlaid Near Seat
- Controls float as a small popup anchored just above the local player's seat tile
- Same buttons, same raise input
- Useful on larger screens where the bottom bar feels distant from the table

**Implementation note:** Both modes are separate components (`<BottomActionBar />` and `<OverlayActionBar />`). A single boolean in Zustand (`uiStore.actionBarMode`) switches between them. To remove one mode permanently, delete that component file and the toggle option — no other code changes needed.

Controls are only interactive when `table.current_action_seat === localPlayer.seat`.

---

## Section 13.5 — Chip & Pot Animations

**All chip animations use GSAP.**

### Chip Stack Visuals
- Chips are rendered as stacked SVG circles with denomination colors
- Standard denominations: white (1), red (5), green (25), black (100), purple (500), yellow (1000)
- Stack height and chip count proportional to amount

### Pot Movement (GSAP)
- When a hand ends and winner(s) are determined, chips animate from the center pot to the winner's seat
- Number of animated chip tokens scales with pot size as a percentage of total chips in play:
  - < 10% of table chips → 3 tokens
  - 10–30% → 6 tokens
  - 30–60% → 12 tokens
  - > 60% → 20 tokens (full explosion)
- For split pots: chips split visually and travel to each winner simultaneously
- Side pots resolve sequentially (smallest side pot first), with a short delay between each

### Bet-to-Pot Collection
- At end of each betting street, player bet stacks animate into the center pot (GSAP stagger)

---

## Section 13.6 — Sound Effects

**Library: Howler.js**

| Event | Sound |
|---|---|
| Card dealt to player | Soft card slide |
| Community card revealed | Heavier card flip |
| Chip bet placed | Single chip clink |
| Pot collected (small) | Few chips clink |
| Pot collected (large) | Chip cascade |
| Your turn | Subtle notification chime |
| Fold | Card slide away |
| All-in | Chip slam |
| Vote banner appears | Soft alert tone |

All sounds are preloaded on table join. A mute toggle is available in the top bar options menu.

---

## Section 13.7 — Spectator Mode

Players who join a table but have not taken a seat are spectators:
- Can see all face-up cards (community cards, revealed hole cards, showdown hands)
- Cannot see any player's face-down hole cards
- No action controls rendered
- See pot, bets, stack sizes, and game phase
- A "Take a Seat" button appears in the center when empty seats exist
- Spectator count shown in top bar

---

## Section 13.8 — Sit Down / Stand Up Flow

### Sitting Down
1. Player clicks an empty seat
2. Modal appears: "Enter starting chip count" (numeric input)
3. Player submits → request sent to host
4. Seat shows "Pending approval" state with player name + chip count
5. Host sees approval prompt (banner or modal); approves or rejects
6. On approval: player is seated, chips added to their stack, `POST /tables/:id/join` completes
7. On rejection: seat returns to empty, player remains spectator

### Standing Up
1. Seated player clicks their own seat tile or uses the Options menu → "Stand Up"
2. Confirmation: "Stand up and return to spectator view?"
3. On confirm: player's seat is freed, they move to spectator view, their stack is cleared
4. Can only stand up between hands (button is disabled mid-hand; shows "Available after this hand")

### Host Controls (per player)
Available via a long-press or right-click on any seat tile (or Options → Manage Players):
- **Stand up player** — moves them to spectator, frees seat (between hands only)
- **Force remove** — disconnects and removes them from the table entirely
- **Approve / reject buy-in** — responds to pending sit-down requests

### Disconnect Behavior
- If a seated player disconnects without standing up, their seat shows `disconnected` badge
- 30-second grace window (per backend spec): if they reconnect within 30s, their turn resumes
- After 30s: auto-check if legal, else auto-fold
- Seat is held for the disconnected player — they can reconnect and resume
- Host can force-stand a disconnected player via host controls

---

## Section 13.9 — Pause & Rule Change Vote

### Pause Game
- Any player can trigger "Pause before next hand" via Options menu
- A banner appears: "Game will pause before the next hand starts — requested by [name]"
- An "Unpause" button appears for any player to cancel the pause
- When the hand ends, game pauses at the `between_hands` phase
- While paused: no new hand starts, but players can chat/spectate freely

### Proposing a Rule Change
- Any player can open the rule change modal via Options → "Propose Rule Change"
- The modal shows the current `TableRules` with editable fields (same layout as Create Table advanced form)
- Player submits → a `propose_rule_change` WS message is sent
- Game automatically pauses before next hand (same mechanism as manual pause)

### Admin Force Change
- Admin sees an additional "Force Change (no vote)" button in the same modal
- Force change takes effect at next hand start, no vote required
- All players see a banner: "Host changed rules to [mode]. Game resumes next hand."

### Vote Banner
- A non-blocking banner slides down from the top of the screen (Framer Motion)
- Shows: proposed mode name + key changed fields (e.g. "NLH 10/20 → NL Shortdeck 10/20")
- Shows: current tally `For: X | Against: Y` — updates live via WS
- Each player sees: "Vote For" / "Vote Against" buttons (disappear after they vote)
- Vote ends automatically when simple majority is reached (> half of seated players)
- If vote passes: banner updates to "Rule change approved — new rules take effect next hand", game unpauses with new rules
- If vote fails: banner updates to "Rule change rejected — resuming with current rules", game unpauses
- Banner auto-dismisses after 5 seconds following resolution

---

## Section 13.10 — Board & Showdown

### Community Cards
- Cards animate in from the deck area (top of oval) using Framer Motion on each street
- Flop: 3 cards deal in staggered sequence
- Turn / River: single card flips in

### Showdown
- All remaining players' hole cards flip face-up (Framer Motion card flip)
- Best hand is highlighted (glow outline on the 5 winning cards)
- Hand rank label shown below each player's seat ("Full House", "Flush", etc.)
- Winner's seat pulses with a win highlight
- Chips animate to winner (GSAP — see Section 13.5)

### Between Hands
- Cards sweep off the table (Framer Motion exit animation)
- Dealer button rotates to next seat
- If game is paused: "Waiting to resume…" shown in center of table
- If a vote is pending: vote banner remains visible

---

## Section 13.11 — Top Bar & Options

### Top Bar (always visible)
- Left: Options / hamburger menu
- Center: Table name
- Right: Game mode + blinds (e.g. "NLH 10 / 20"), mute toggle

### Options Menu (slide-in drawer)
- Toggle action bar position (bottom bar ↔ overlay)
- Mute / unmute sounds
- Propose rule change
- Pause before next hand
- Stand up (if seated)
- Return to lobby (leaves table, goes to `/`)
- Host only: Manage players

---

## Section 13.12 — WebSocket State (Zustand)

```
useGameStore
  table: Table | null          ← full snapshot from server
  localSeq: number             ← last seq received
  localPlayerId: string        ← session_id from JWT
  phase: string                ← mirrors table.phase
  pendingVote: ModeVote | null
  actionBarMode: 'bottom' | 'overlay'
  isPaused: boolean

  actions:
    connect(tableId, token)    ← opens WS, registers message handler
    disconnect()
    applyPatch(patch)          ← merges state_patch from incremental events
    applySnapshot(snapshot)    ← full state replace on connect/reconnect
    sendAction(action, amount)
    sendVote(direction)
    requestReplay(fromSeq)
```

On every incoming WS message:
1. Check `event.seq === localSeq + 1` — if not, call `requestReplay`
2. Route by `event.type`: `state_snapshot` → `applySnapshot`, `event` → `applyPatch`, `deal` → update local hole cards only
3. Trigger sound effect based on event type
4. Trigger GSAP/Framer Motion animation based on event type

---

## Section 13.13 — New Backend Requirements

The following backend additions are needed to support the frontend design:

### New WS Message Types (client → server)
| Message | Payload | Description |
|---|---|---|
| `propose_rule_change` | `{ proposed_rules: TableRules }` | Any player proposes a rule change |
| `force_rule_change` | `{ proposed_rules: TableRules }` | Admin only; skips vote |
| `pause_request` | `{}` | Any player requests pause before next hand |
| `unpause_request` | `{}` | Any player cancels pause |
| `reveal_card` | `{ card_index: 0 \| 1 }` | Player reveals one hole card to all |
| `rabbit_hunt_request` | `{}` | Winner requests to see remaining community cards |
| `sit_down_request` | `{ seat: int, chips: int }` | Player requests to take a seat |
| `approve_sit_down` | `{ session_id: str }` | Host approves a pending sit-down |
| `reject_sit_down` | `{ session_id: str }` | Host rejects a pending sit-down |
| `stand_up` | `{}` | Player stands up from their seat |
| `host_stand_up` | `{ session_id: str }` | Host stands up another player |
| `host_remove_player` | `{ session_id: str }` | Host force-removes a player |

### New WS Message Types (server → client)
| Message | Description |
|---|---|
| `sit_down_request` broadcast | Notifies host of pending sit-down request |
| `sit_down_approved` / `sit_down_rejected` | Notifies requesting player of outcome |
| `player_stood_up` | Seat freed, spectator list updated |
| `player_removed` | Player removed from table |
| `card_revealed` | `{ session_id, card_index, card }` — broadcast hole card reveal |
| `rabbit_hunt` | `{ cards: Card[] }` — ghost community cards for winner only |
| `game_paused` | Game will pause before next hand |
| `game_unpaused` | Game resumed (with or without rule change) |
| `vote_update` | `{ votes_for, votes_against, total_eligible }` — live tally |
| `vote_resolved` | `{ passed: bool, new_rules?: TableRules }` |

### New `TableRules` Fields
- `timer_enabled: bool` — whether a per-turn timer is active
- `timer_seconds: int` — duration in seconds (only used if `timer_enabled`)

### New `Table` State Fields
- `spectators: list[str]` — session_ids of connected non-seated players
- `pending_sit_requests: list[{ session_id, seat, chips }]` — awaiting host approval
- `is_paused: bool` — game is paused before next hand
- `pause_requested_by: str | None` — session_id who requested pause

### New `Player` State Fields
- `is_revealed: list[bool]` — `[False, False]` per hole card; flips to `True` on reveal

---

## Build Order (Frontend)

| Step | Component | Notes |
|---|---|---|
| 1 | Vite + React scaffold | Tailwind v4, React Router, Zustand wired up |
| 2 | Lobby page | Table list, name entry, create table form |
| 3 | Zustand WS store | connect, applySnapshot, applyPatch, sendAction |
| 4 | Oval table layout | Seat positioning math, empty/occupied states |
| 5 | Seat tile | Name, stack, cards, badges |
| 6 | Action controls | Both modes (bottom bar + overlay), mode toggle |
| 7 | Card animations | Framer Motion deal, flip, reveal |
| 8 | Chip animations | GSAP pot movement, bet collection |
| 9 | Sound effects | Howler.js integration |
| 10 | Sit down / stand up flow | Request → approval → seat |
| 11 | Pause + vote UI | Banner, tally, resolution |
| 12 | Showdown + rabbit hunt | Hand highlight, ghost cards |
| 13 | Host controls | Manage players drawer |
| 14 | Mobile polish | Touch targets, responsive oval scaling |
