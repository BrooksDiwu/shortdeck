import { create } from 'zustand'
import type { Table, Card, ServerMessage, ClientMessage, ActionBarMode } from '@/types'
import { useSoundStore } from './soundStore'

export interface ChatMessage {
  session_id: string
  sender: string
  text: string
  timestamp: string
}

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'
const DEAL_ANIMATION_TOTAL_MS = 1800
const CARD_SOUND_INTERVAL_MS = 70

function playCardBurst(play: (key: 'card_deal' | 'community_card') => void, key: 'card_deal' | 'community_card', count: number) {
  if (count <= 0) return
  for (let i = 0; i < count; i += 1) {
    window.setTimeout(() => play(key), i * CARD_SOUND_INTERVAL_MS)
  }
}

function pickPotSound(table: Table | null, amount: number): 'pot_collected_small' | 'pot_collected_large' {
  if (!table || amount <= 0) return 'pot_collected_small'
  const threshold = Math.max(table.rules.big_blind * 10, 100)
  return amount >= threshold ? 'pot_collected_large' : 'pot_collected_small'
}

export type RabbitHuntCards = Card[]

interface GameState {
  table: Table | null
  localSeq: number
  localPlayerId: string | null
  holeCards: Card[]
  rabbitHuntCards: Card[]
  actionBarMode: ActionBarMode
  ws: WebSocket | null
  connectionState: 'disconnected' | 'connecting' | 'connected' | 'error'
  connectionError: string | null
  voteResolution: { passed: boolean; newRules?: Table['rules'] } | null
  chatMessages: ChatMessage[]
  serverError: string | null

  connect: (tableId: string, token: string, playerId: string) => void
  disconnect: () => void
  applySnapshot: (snapshot: Table, seq: number) => void
  applyPatch: (event: Record<string, unknown>) => void
  sendMessage: (msg: ClientMessage) => void
  setActionBarMode: (mode: ActionBarMode) => void
  clearVoteResolution: () => void
  clearRabbitHunt: () => void
  clearServerError: () => void
}

export const useGameStore = create<GameState>((set, get) => ({
  table: null,
  localSeq: 0,
  localPlayerId: null,
  holeCards: [],
  rabbitHuntCards: [],
  actionBarMode: 'bottom',
  ws: null,
  connectionState: 'disconnected',
  connectionError: null,
  voteResolution: null,
  chatMessages: [],
  serverError: null,

  connect: (tableId: string, token: string, playerId: string) => {
    const existing = get().ws
    if (existing) {
      existing.close()
    }

    set({ connectionState: 'connecting', localPlayerId: playerId, holeCards: [], localSeq: 0, connectionError: null })
    let dealAnimationToken = 0

    const ws = new WebSocket(`${WS_URL}/ws/table/${tableId}?token=${token}`)

    ws.onopen = () => {
      set({ connectionState: 'connected', ws })
    }

    ws.onclose = (event: CloseEvent) => {
      if (event.code === 4003) {
        set({ connectionState: 'error', connectionError: event.reason || 'Name already taken by a connected player', ws: null })
      } else {
        set({ connectionState: 'disconnected', connectionError: null, ws: null })
      }
    }

    ws.onerror = () => {
      set({ connectionState: 'error' })
    }

    ws.onmessage = (event: MessageEvent) => {
      let msg: ServerMessage
      try {
        msg = JSON.parse(event.data as string) as ServerMessage
      } catch {
        console.error('Invalid WS message', event.data)
        return
      }

      const { localSeq, sendMessage } = get()
      const sound = useSoundStore.getState()

      console.log('[ws.onmessage] type:', msg.type, JSON.stringify(msg))

      if (msg.type === 'chat_message') {
        set((state) => ({
          chatMessages: [...state.chatMessages, {
            session_id: msg.session_id,
            sender: msg.sender,
            text: msg.text,
            timestamp: msg.timestamp,
          }],
        }))
        return
      }

      if ((msg as unknown as { type: string }).type === 'error') {
        const errMsg = msg as unknown as { message: string }
        set({ serverError: errMsg.message })
        return
      }

      if (msg.type === 'state_snapshot') {
        // Backend sends players as a list; convert to Record<session_id, Player>
        const playersArr = (msg as unknown as Record<string, unknown>).players as Array<Record<string, unknown>>
        const playersMap = Object.fromEntries(
          playersArr.map((p) => [p.session_id as string, p])
        ) as unknown as Table['players']
        const raw = msg as unknown as Record<string, unknown>
        const snapshot = { ...raw, players: playersMap, admin_id: raw.admin_id ?? '', player_join_order: raw.player_join_order ?? [] } as unknown as Table
        const prevTable = get().table
        const enteredNewPreflopHand =
          !!prevTable &&
          snapshot.phase === 'preflop' &&
          snapshot.hand_number > prevTable.hand_number
        if (enteredNewPreflopHand) {
          const activeCount = Object.values(snapshot.players).filter(
            (p) => p.status !== 'sitting_out' && p.status !== 'disconnected'
          ).length
          const totalDealtCards = activeCount * snapshot.rules.hole_cards_count
          if (totalDealtCards > 0) {
            const intervalMs = Math.max(
              35,
              Math.floor(DEAL_ANIMATION_TOTAL_MS / Math.max(totalDealtCards - 1, 1))
            )
            for (let i = 0; i < totalDealtCards; i += 1) {
              window.setTimeout(() => sound.play('card_deal'), i * intervalMs)
            }
          }
        }
        get().applySnapshot(snapshot, (msg as unknown as { seq: number }).seq)
        return
      }

      if (msg.type === 'deal') {
        dealAnimationToken += 1
        const tokenForThisDeal = dealAnimationToken
        const cards = msg.hole_cards ?? []
        set({ holeCards: [] })
        if (cards.length === 0) return

        const intervalMs = Math.max(
          120,
          Math.floor(DEAL_ANIMATION_TOTAL_MS / Math.max(cards.length, 1))
        )
        cards.forEach((card, index) => {
          window.setTimeout(() => {
            if (tokenForThisDeal !== dealAnimationToken) return
            set((state) => ({ holeCards: [...state.holeCards, card] }))
          }, index * intervalMs)
        })
        return
      }

      if (msg.type === 'rabbit_hunt') {
        set({ rabbitHuntCards: msg.cards })
        return
      }

      if (msg.type === 'sit_down_request') {
        console.log('[sit_down_request] received:', msg)
        const m = msg as unknown as { pending_sit_requests: Table['pending_sit_requests'] }
        console.log('[sit_down_request] pending_sit_requests:', m.pending_sit_requests)
        set((state) => state.table ? { table: { ...state.table, pending_sit_requests: m.pending_sit_requests } } : {})
        return
      }

      if (msg.type === 'sit_down_approved') {
        // Personal message to admin with the real updated pending list
        const m = msg as unknown as { pending_sit_requests: Table['pending_sit_requests'] }
        if (m.pending_sit_requests !== undefined) {
          set((state) => state.table ? { table: { ...state.table, pending_sit_requests: m.pending_sit_requests } } : {})
        }
        return
      }

      if (msg.type === 'sit_down_rejected') {
        // Personal message to admin with the real updated pending list
        const m = msg as unknown as { pending_sit_requests: Table['pending_sit_requests'] }
        if (m.pending_sit_requests !== undefined) {
          set((state) => state.table ? { table: { ...state.table, pending_sit_requests: m.pending_sit_requests } } : {})
        }
        return
      }

      if (msg.type === 'card_revealed') {
        set((state) => {
          if (!state.table) return {}
          const player = state.table.players[msg.session_id]
          if (!player) return {}
          const newRevealed = [...player.is_revealed]
          newRevealed[msg.card_index] = true
          const newHoleCards = [...player.hole_cards]
          newHoleCards[msg.card_index] = msg.card
          return {
            table: {
              ...state.table,
              players: {
                ...state.table.players,
                [msg.session_id]: { ...player, is_revealed: newRevealed, hole_cards: newHoleCards },
              },
            },
          }
        })
        return
      }

      // Replay response: backend wraps replayed events in {type:'replay', event:{...}}
      if ((msg as unknown as { type: string }).type === 'replay') {
        const replayMsg = msg as unknown as { type: 'replay'; event: Record<string, unknown> }
        const ev = replayMsg.event
        const evSeq = ev.seq as number
        const curSeq = get().localSeq
        if (evSeq === curSeq + 1) {
          get().applyPatch(ev)
        } else if (evSeq <= curSeq) {
          // already applied, ignore
        } else {
          // still a gap — request again from current position
          sendMessage({ type: 'replay_request', from_seq: curSeq + 1 })
        }
        return
      }

      // Incremental events with seq tracking
      if (msg.type === 'event') {
        const eventMsg = msg as { type: 'event'; seq: number; [key: string]: unknown }
        if (eventMsg.seq !== localSeq + 1) {
          // Gap detected — request replay
          console.warn('[ws] gap detected: expected seq', localSeq + 1, 'got', eventMsg.seq, '— requesting replay')
          sendMessage({ type: 'replay_request', from_seq: localSeq + 1 })
          return
        }
        const beforeTable = get().table
        const beforePrimaryCount = beforeTable?.board.primary.length ?? 0
        const beforeSecondaryCount = beforeTable?.board.secondary.length ?? 0
        const beforeFrontBets = beforeTable
          ? Object.values(beforeTable.players).reduce((sum, p) => sum + p.current_bet, 0)
          : 0
        console.log('[event] applying patch seq:', eventMsg.seq, 'event_type:', eventMsg.event_type, 'current_action_seat:', eventMsg.current_action_seat, 'state_patch:', JSON.stringify((eventMsg as Record<string,unknown>).state_patch))
        get().applyPatch(eventMsg)
        const afterTable = get().table
        // Trigger sounds based on event sub-type
        const evType = eventMsg.event_type as string | undefined
        if (evType === 'card_revealed') {
          const revealMsg = eventMsg as unknown as { session_id: string; card_index: number; card: Record<string, unknown> }
          set((state) => {
            if (!state.table) return {}
            const player = state.table.players[revealMsg.session_id]
            if (!player) return {}
            const newRevealed = [...(player.is_revealed ?? [])]
            newRevealed[revealMsg.card_index] = true
            const newHoleCards = [...(player.hole_cards ?? [])]
            newHoleCards[revealMsg.card_index] = revealMsg.card as unknown as Card
            return {
              table: {
                ...state.table,
                players: {
                  ...state.table.players,
                  [revealMsg.session_id]: { ...player, is_revealed: newRevealed, hole_cards: newHoleCards },
                },
              },
            }
          })
        }
        if (evType) {
          if (evType === 'action' && eventMsg.action === 'fold') sound.play('fold')
          else if (evType === 'action' && eventMsg.action === 'check') sound.play('check')
          else if (evType === 'action' && eventMsg.action === 'all_in') sound.play('all_in')
          else if (evType === 'action' && (eventMsg.action === 'raise' || eventMsg.action === 'call' || eventMsg.action === 'all_in')) sound.play('chip_bet')
          else if (evType === 'community_cards') {
            const afterPrimaryCount = afterTable?.board.primary.length ?? 0
            const afterSecondaryCount = afterTable?.board.secondary.length ?? 0
            const newCardCount = Math.max(
              0,
              (afterPrimaryCount + afterSecondaryCount) - (beforePrimaryCount + beforeSecondaryCount)
            )
            playCardBurst(sound.play, 'community_card', newCardCount)
            if (beforeFrontBets > 0) {
              sound.play(pickPotSound(beforeTable ?? null, beforeFrontBets))
            }
          } else if (evType === 'hand_complete') {
            const winners = (eventMsg.winners as Record<string, number> | undefined) ?? {}
            const awarded = Object.values(winners).reduce((sum, amount) => sum + amount, 0)
            sound.play(pickPotSound(beforeTable ?? null, awarded))
          }
          else if (evType === 'game_paused' || evType === 'vote_update') sound.play('vote_banner')
          else if (evType === 'vote_resolved') {
            const passed = eventMsg.passed as boolean
            const newRules = eventMsg.new_rules as Table['rules'] | undefined
            set({ voteResolution: { passed, newRules } })
          }
        }
        const currentSeat = get().table?.current_action_seat
        const localPlayer = get().table && get().localPlayerId
          ? Object.values(get().table!.players).find(p => p.session_id === get().localPlayerId)
          : null
        if (localPlayer && currentSeat === localPlayer.seat) {
          sound.play('your_turn')
        }
      }
    }
  },

  disconnect: () => {
    const { ws } = get()
    if (ws) ws.close()
    set({ ws: null, connectionState: 'disconnected', table: null, holeCards: [], localSeq: 0, chatMessages: [] })
  },

  applySnapshot: (snapshot: Table, seq: number) => {
    set({ table: snapshot, localSeq: seq })
  },

  applyPatch: (event: Record<string, unknown>) => {
    set((state) => {
      if (!state.table) return {}
      const seq = event.seq as number
      const evType = event.event_type as string | undefined

      // Backend nests table fields under state_patch — flatten into event
      const patch = typeof event.state_patch === 'object' && event.state_patch !== null
        ? { ...event, ...(event.state_patch as Record<string, unknown>) }
        : event

      // Merge top-level table fields from event
      const tableUpdates: Partial<Table> = {}

      if ('phase' in patch) tableUpdates.phase = patch.phase as Table['phase']
      if ('pot' in patch) tableUpdates.pot = patch.pot as number
      if ('side_pots' in patch) tableUpdates.side_pots = patch.side_pots as Table['side_pots']
      if ('board' in patch) tableUpdates.board = patch.board as Table['board']
      if ('current_action_seat' in patch) tableUpdates.current_action_seat = patch.current_action_seat as number
      if ('dealer_seat' in patch) tableUpdates.dealer_seat = patch.dealer_seat as number
      if ('hand_number' in patch) tableUpdates.hand_number = patch.hand_number as number
      if ('pending_vote' in patch) tableUpdates.pending_vote = patch.pending_vote as Table['pending_vote']
      if ('is_paused' in patch) tableUpdates.is_paused = patch.is_paused as boolean
      if ('pause_requested_by' in patch) tableUpdates.pause_requested_by = patch.pause_requested_by as string | null
      if ('spectators' in patch) tableUpdates.spectators = patch.spectators as string[]
      if ('pending_sit_requests' in patch) tableUpdates.pending_sit_requests = patch.pending_sit_requests as Table['pending_sit_requests']
      if ('player_join_order' in patch) tableUpdates.player_join_order = patch.player_join_order as string[]
      if ('admin_id' in patch) tableUpdates.admin_id = patch.admin_id as string
      if ('hand_log' in patch) tableUpdates.hand_log = patch.hand_log as Table['hand_log']

      // Handle event_type-implied state changes not present as explicit fields
      if (evType === 'game_paused') {
        tableUpdates.is_paused = true
        tableUpdates.pause_requested_by = patch.requested_by as string | null ?? null
      } else if (evType === 'game_unpaused') {
        tableUpdates.is_paused = false
        tableUpdates.pause_requested_by = null
      } else if (evType === 'vote_resolved') {
        const passed = patch.passed as boolean
        if (passed && patch.new_rules) {
          tableUpdates.rules = patch.new_rules as Table['rules']
        }
        tableUpdates.pending_vote = null
        tableUpdates.is_paused = false
        tableUpdates.pause_requested_by = null
      }

      // Player updates
      let newPlayers = { ...state.table.players }
      if ('players' in patch && patch.players && typeof patch.players === 'object') {
        const playerUpdates = patch.players as Record<string, Partial<Table['players'][string]>>
        for (const [id, update] of Object.entries(playerUpdates)) {
          if (newPlayers[id]) {
            newPlayers[id] = { ...newPlayers[id], ...update }
          } else if (update) {
            newPlayers[id] = update as Table['players'][string]
          }
        }
      }
      if ('removed_players' in patch && Array.isArray(patch.removed_players)) {
        for (const id of patch.removed_players as string[]) {
          delete newPlayers[id]
        }
      }

      return {
        localSeq: seq,
        table: { ...state.table, ...tableUpdates, players: newPlayers },
      }
    })
  },

  sendMessage: (msg: ClientMessage) => {
    const { ws } = get()
    console.log('[sendMessage] msg:', msg, 'ws:', ws?.readyState, 'OPEN=', WebSocket.OPEN)
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg))
      console.log('[sendMessage] sent OK')
    } else {
      console.warn('[sendMessage] DROPPED — ws not open. readyState:', ws?.readyState, 'ws:', ws)
    }
  },

  setActionBarMode: (mode: ActionBarMode) => {
    set({ actionBarMode: mode })
  },

  clearVoteResolution: () => {
    set({ voteResolution: null })
  },

  clearRabbitHunt: () => {
    set({ rabbitHuntCards: [] })
  },

  clearServerError: () => {
    set({ serverError: null })
  },
}))
