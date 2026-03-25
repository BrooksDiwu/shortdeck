import { create } from 'zustand'
import type { Table, Card, ServerMessage, ClientMessage, ActionBarMode } from '@/types'
import { useSoundStore } from './soundStore'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'

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
  voteResolution: { passed: boolean; newRules?: Table['rules'] } | null

  connect: (tableId: string, token: string, playerId: string) => void
  disconnect: () => void
  applySnapshot: (snapshot: Table, seq: number) => void
  applyPatch: (event: Record<string, unknown>) => void
  sendMessage: (msg: ClientMessage) => void
  setActionBarMode: (mode: ActionBarMode) => void
  clearVoteResolution: () => void
  clearRabbitHunt: () => void
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
  voteResolution: null,

  connect: (tableId: string, token: string, playerId: string) => {
    const existing = get().ws
    if (existing) {
      existing.close()
    }

    set({ connectionState: 'connecting', localPlayerId: playerId, holeCards: [], localSeq: 0 })

    const ws = new WebSocket(`${WS_URL}/ws/table/${tableId}?token=${token}`)

    ws.onopen = () => {
      set({ connectionState: 'connected', ws })
    }

    ws.onclose = () => {
      set({ connectionState: 'disconnected', ws: null })
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

      if (msg.type === 'state_snapshot') {
        // Backend sends players as a list; convert to Record<session_id, Player>
        const playersArr = (msg as unknown as Record<string, unknown>).players as Array<Record<string, unknown>>
        const playersMap = Object.fromEntries(
          playersArr.map((p) => [p.session_id as string, p])
        ) as Table['players']
        const raw = msg as unknown as Record<string, unknown>
        const snapshot = { ...raw, players: playersMap, admin_id: raw.admin_id ?? '', player_join_order: raw.player_join_order ?? [] } as unknown as Table
        get().applySnapshot(snapshot, (msg as unknown as { seq: number }).seq)
        return
      }

      if (msg.type === 'deal') {
        set({ holeCards: msg.hole_cards })
        sound.play('card_deal')
        return
      }

      if (msg.type === 'rabbit_hunt') {
        set({ rabbitHuntCards: msg.cards })
        return
      }

      if (msg.type === 'game_paused') {
        set((state) => state.table ? { table: { ...state.table, is_paused: true } } : {})
        return
      }

      if (msg.type === 'game_unpaused') {
        set((state) => state.table ? { table: { ...state.table, is_paused: false } } : {})
        return
      }

      if (msg.type === 'vote_update') {
        set((state) => {
          if (!state.table?.pending_vote) return {}
          return {
            table: {
              ...state.table,
              pending_vote: {
                ...state.table.pending_vote,
                votes_for: Array(msg.votes_for).fill(''),
                votes_against: Array(msg.votes_against).fill(''),
              },
            },
          }
        })
        sound.play('vote_banner')
        return
      }

      if (msg.type === 'vote_resolved') {
        set({ voteResolution: { passed: msg.passed, newRules: msg.new_rules } })
        if (msg.passed && msg.new_rules) {
          set((state) => state.table ? { table: { ...state.table, rules: msg.new_rules!, pending_vote: null } } : {})
        } else {
          set((state) => state.table ? { table: { ...state.table, pending_vote: null } } : {})
        }
        return
      }

      if (msg.type === 'sit_down_request') {
        const m = msg as unknown as { pending_sit_requests: Table['pending_sit_requests'] }
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

      // Incremental events with seq tracking
      if (msg.type === 'event') {
        const eventMsg = msg as { type: 'event'; seq: number; [key: string]: unknown }
        if (eventMsg.seq !== localSeq + 1) {
          // Gap detected — request replay
          sendMessage({ type: 'replay_request', from_seq: localSeq + 1 })
          return
        }
        get().applyPatch(eventMsg)
        // Trigger sounds based on event sub-type
        const evType = eventMsg.event_type as string | undefined
        if (evType) {
          if (evType === 'action' && eventMsg.action === 'fold') sound.play('fold')
          else if (evType === 'action' && eventMsg.action === 'all_in') sound.play('all_in')
          else if (evType === 'action' && (eventMsg.action === 'raise' || eventMsg.action === 'call')) sound.play('chip_bet')
          else if (evType === 'community_cards') sound.play('community_card')
          else if (evType === 'hand_complete') sound.play('pot_collected_large')
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
    set({ ws: null, connectionState: 'disconnected', table: null, holeCards: [], localSeq: 0 })
  },

  applySnapshot: (snapshot: Table, seq: number) => {
    set({ table: snapshot, localSeq: seq })
  },

  applyPatch: (event: Record<string, unknown>) => {
    set((state) => {
      if (!state.table) return {}
      const seq = event.seq as number

      // Merge top-level table fields from event
      const tableUpdates: Partial<Table> = {}

      if ('phase' in event) tableUpdates.phase = event.phase as Table['phase']
      if ('pot' in event) tableUpdates.pot = event.pot as number
      if ('side_pots' in event) tableUpdates.side_pots = event.side_pots as Table['side_pots']
      if ('board' in event) tableUpdates.board = event.board as Table['board']
      if ('current_action_seat' in event) tableUpdates.current_action_seat = event.current_action_seat as number
      if ('dealer_seat' in event) tableUpdates.dealer_seat = event.dealer_seat as number
      if ('hand_number' in event) tableUpdates.hand_number = event.hand_number as number
      if ('pending_vote' in event) tableUpdates.pending_vote = event.pending_vote as Table['pending_vote']
      if ('is_paused' in event) tableUpdates.is_paused = event.is_paused as boolean
      if ('pause_requested_by' in event) tableUpdates.pause_requested_by = event.pause_requested_by as string | null
      if ('spectators' in event) tableUpdates.spectators = event.spectators as string[]
      if ('pending_sit_requests' in event) tableUpdates.pending_sit_requests = event.pending_sit_requests as Table['pending_sit_requests']
      if ('player_join_order' in event) tableUpdates.player_join_order = event.player_join_order as string[]
      if ('admin_id' in event) tableUpdates.admin_id = event.admin_id as string

      // Player updates
      let newPlayers = { ...state.table.players }
      if ('players' in event && event.players && typeof event.players === 'object') {
        const playerUpdates = event.players as Record<string, Partial<Table['players'][string]>>
        for (const [id, update] of Object.entries(playerUpdates)) {
          if (newPlayers[id]) {
            newPlayers[id] = { ...newPlayers[id], ...update }
          } else if (update) {
            newPlayers[id] = update as Table['players'][string]
          }
        }
      }
      if ('removed_players' in event && Array.isArray(event.removed_players)) {
        for (const id of event.removed_players as string[]) {
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
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg))
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
}))
