# Shortdeck Holdem — AGENTS.md

> **Testing environment:** Always activate `conda activate poker` before running tests or any Python commands in this repo.

## Project Overview
Real-time multiplayer poker webapp supporting Texas Hold'em and Shortdeck Hold'em. FastAPI backend with WebSocket gameplay, Redis for active state, PostgreSQL for durable history, React/Vite frontend (TODO).

## Stack
- **Backend:** Python + FastAPI, WebSockets
- **Active state:** Redis (snapshot + append-only event log + pub/sub + distributed locks)
- **Durable storage:** PostgreSQL (hand history, sessions)
- **Frontend:** React + Vite (`frontend/` — not yet implemented)
- **Prod infra:** AWS ECS Fargate + ElastiCache + RDS + ALB + CloudFront

## Key Backend Modules
- `game/card.py`, `game/deck.py` — card primitives; Shortdeck removes ranks 2–5 (36-card deck)
- `game/hand_evaluator.py` — hand evaluation; Shortdeck ranks flush above full house
- `game/table_rules.py` — `TableRules` dataclass drives all variant/rule config
- `game/variants/` — `holdem.py`, `shortdeck.py` extend `base.py`
- `game/player.py`, `game/table.py` — pure state dataclasses, JSON-serializable
- `game/betting.py` — action validation, side pot construction, pot-limit/no-limit logic
- `game/engine.py` — orchestrates full hand lifecycle; reads `TableRules`, no hardcoded variant logic
- `websocket/manager.py`, `websocket/router.py` — JWT auth at handshake, pub/sub broadcast
- `api/tables.py`, `api/sessions.py` — REST pre-game setup; all in-game actions via WebSocket
- `services/table_service.py` — Redis lock/read/write pattern for every state mutation
- `backend/main.py`, `config.py`, `dependencies.py` — app entry, env config, FastAPI deps

## Critical Design Rules
- Every table mutation: acquire Redis lock → read → mutate → increment `action_seq` → append event → write snapshot → publish → release lock
- Shortdeck: ace plays low in A-6-7-8-9 straights; flush beats full house
- Side pots built by sorting `total_in` ascending; odd chips go to first active player left of dealer
- Admin transfers immediately on disconnect (not after grace window); new admin keeps rights on reconnect
- Disconnect during turn: 30s grace → auto-check if legal, else auto-fold
- Mode changes apply between hands only; player stacks carry over across variants
