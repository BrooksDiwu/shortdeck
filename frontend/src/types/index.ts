export interface Card {
  rank: string // "A","K","Q","J","T","9",...,"2"
  suit: string // "s","h","d","c"
}

export interface TableRulesSchema {
  variant: 'holdem' | 'shortdeck'
  betting: 'no_limit' | 'pot_limit'
  small_blind: number
  big_blind: number
  denomination: 'chips' | 'usd'
  hole_cards_count: number
  extra_hole_card: boolean
  must_use_exactly_two_hole_cards: boolean
  extra_board: boolean
  extra_flop: boolean
  street_modifiers: Record<string, number>
  max_players: number
  allow_rebuy: boolean
  timer_enabled: boolean
  timer_seconds: number
}

export interface Player {
  session_id: string
  name: string
  stack: number
  hole_cards: Card[]
  seat: number
  status: 'active' | 'folded' | 'all_in' | 'sitting_out' | 'disconnected'
  is_admin: boolean
  current_bet: number
  total_in: number
  is_revealed: boolean[]
  can_request_rebuy?: boolean
  buy_in: number
  sit_in_next_hand?: boolean
}

export interface LeaderboardEntry {
  session_id: string
  name: string
  buy_in: number
  final_stack: number
}

export interface SidePot {
  amount: number
  eligible: string[]
}

export interface ModeVote {
  proposed_rules: TableRulesSchema
  proposed_by: string
  votes_for: string[]
  votes_against: string[]
  expires_at: string
}

export interface PendingSitRequest {
  session_id: string
  seat: number
  chips: number
  name?: string
}

export interface HandLogWinner {
  session_id: string
  name: string
  amount_won: number
  hand_description: string | null
}

export interface HandLogShownHand {
  session_id: string
  name: string
  seat: number
  hole_cards: Card[]
  best_hand: string
  amount_won: number
}

export interface HandLogEntry {
  hand_number: number
  completed_at: string
  showdown: boolean
  pot: number
  board: { primary: Card[]; secondary: Card[] }
  winners: HandLogWinner[]
  shown_hands: HandLogShownHand[]
  action_lines: string[]
}

export interface Table {
  table_id: string
  players: Record<string, Player>
  player_join_order: string[]
  admin_id: string
  rules: TableRulesSchema
  board: { primary: Card[]; secondary: Card[] }
  pot: number
  side_pots: SidePot[]
  dealer_seat: number
  current_action_seat: number
  phase: 'waiting' | 'preflop' | 'flop' | 'turn' | 'river' | 'showdown' | 'between_hands'
  hand_number: number
  action_seq: number
  pending_vote: ModeVote | null
  spectators: string[]
  pending_sit_requests: PendingSitRequest[]
  is_paused: boolean
  pause_requested_by: string | null
  hand_log: HandLogEntry[]
  leaderboard: LeaderboardEntry[]
  pending_rebuys: { session_id: string; amount: number }[]
}

export interface TableResponse {
  table_id: string
  name: string
  rules: TableRulesSchema
  phase: string
  player_count: number
  created_at: string | null
}

// WebSocket message types (client → server)
export type ClientMessage =
  | { type: 'action'; action: 'fold' | 'check' | 'call' | 'raise' | 'all_in'; amount?: number }
  | { type: 'vote'; vote: 'for' | 'against' }
  | { type: 'propose_rule_change'; proposed_rules: TableRulesSchema }
  | { type: 'force_rule_change'; proposed_rules: TableRulesSchema }
  | { type: 'pause_request' }
  | { type: 'unpause_request' }
  | { type: 'reveal_card'; card_index: 0 | 1 }
  | { type: 'rabbit_hunt_request' }
  | { type: 'sit_down_request'; seat: number; chips: number }
  | { type: 'approve_sit_down'; session_id: string }
  | { type: 'reject_sit_down'; session_id: string }
  | { type: 'stand_up' }
  | { type: 'sit_out' }
  | { type: 'sit_in' }
  | { type: 'host_stand_up'; session_id: string }
  | { type: 'host_remove_player'; session_id: string }
  | { type: 'replay_request'; from_seq: number }
  | { type: 'start_hand' }
  | { type: 'chat_message'; text: string }

// WebSocket message types (server → client)
export type ServerMessage =
  | { type: 'state_snapshot'; table: Table; seq: number }
  | { type: 'event'; seq: number; [key: string]: unknown }
  | { type: 'deal'; hole_cards: Card[] }
  | { type: 'sit_down_request'; session_id: string; seat: number; chips: number; name: string }
  | { type: 'sit_down_approved'; session_id: string; seat: number; chips: number; pending_sit_requests?: Table['pending_sit_requests'] }
  | { type: 'sit_down_rejected'; session_id: string; pending_sit_requests?: Table['pending_sit_requests'] }
  | { type: 'player_stood_up'; session_id: string }
  | { type: 'player_removed'; session_id: string }
  | { type: 'card_revealed'; session_id: string; card_index: number; card: Card }
  | { type: 'rabbit_hunt'; cards: Card[] }
  | { type: 'game_paused' }
  | { type: 'game_unpaused' }
  | { type: 'vote_update'; votes_for: number; votes_against: number; total_eligible: number }
  | { type: 'vote_resolved'; passed: boolean; new_rules?: TableRulesSchema }
  | { type: 'chat_message'; session_id: string; sender: string; text: string; timestamp: string }

export type ActionBarMode = 'bottom' | 'overlay'
