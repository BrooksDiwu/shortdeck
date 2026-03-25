import type { TableRulesSchema, Card } from '@/types'

export function getGameModeLabel(rules: TableRulesSchema): string {
  const { variant, betting } = rules
  if (variant === 'holdem' && betting === 'no_limit') return 'NLH'
  if (variant === 'shortdeck' && betting === 'no_limit') return 'NL Shortdeck'
  if (variant === 'holdem' && betting === 'pot_limit') return 'PLO'
  if (variant === 'shortdeck' && betting === 'pot_limit') return 'PLO Shortdeck'
  return 'Unknown'
}

export function formatBlinds(rules: TableRulesSchema): string {
  return `${rules.small_blind} / ${rules.big_blind}`
}

export function formatAmount(amount: number, denomination: 'chips' | 'usd'): string {
  if (denomination === 'usd') {
    return `$${(amount / 100).toFixed(2)}`
  }
  return amount.toLocaleString()
}

export function getCardLabel(card: Card): string {
  const suitSymbol: Record<string, string> = { s: '♠', h: '♥', d: '♦', c: '♣' }
  return `${card.rank}${suitSymbol[card.suit] ?? card.suit}`
}

export function getSuitColor(suit: string): string {
  return suit === 'h' || suit === 'd' ? '#ef4444' : '#f9fafb'
}

export function getSuitSymbol(suit: string): string {
  const map: Record<string, string> = { s: '♠', h: '♥', d: '♦', c: '♣' }
  return map[suit] ?? suit
}

// Polar coordinate math for seat positioning
export function getSeatPosition(
  seatIndex: number,
  totalSeats: number,
  localSeatIndex: number,
  radiusX: number,
  radiusY: number
): { x: number; y: number; angle: number } {
  // Local player is always at the bottom center (270°)
  const localAngle = 270
  const degreesPerSeat = 360 / totalSeats
  const offsetFromLocal = seatIndex - localSeatIndex
  const angleDeg = ((localAngle + offsetFromLocal * degreesPerSeat) % 360 + 360) % 360
  const angleRad = (angleDeg * Math.PI) / 180
  const x = radiusX * Math.cos(angleRad)
  const y = radiusY * Math.sin(angleRad)
  return { x, y, angle: angleDeg }
}

export function getChipTokenCount(potAmount: number, totalChips: number): number {
  if (totalChips === 0) return 3
  const ratio = potAmount / totalChips
  if (ratio < 0.1) return 3
  if (ratio < 0.3) return 6
  if (ratio < 0.6) return 12
  return 20
}

// Determine chip denominations from amount
export const CHIP_DENOMINATIONS = [
  { value: 1000, color: '#eab308' },  // yellow
  { value: 500, color: '#a855f7' },   // purple
  { value: 100, color: '#1f2937' },   // black
  { value: 25, color: '#22c55e' },    // green
  { value: 5, color: '#ef4444' },     // red
  { value: 1, color: '#f9fafb' },     // white
]

export function getChipBreakdown(amount: number): Array<{ value: number; color: string; count: number }> {
  let remaining = amount
  const breakdown: Array<{ value: number; color: string; count: number }> = []
  for (const { value, color } of CHIP_DENOMINATIONS) {
    const count = Math.floor(remaining / value)
    if (count > 0) {
      breakdown.push({ value, color, count })
      remaining -= count * value
    }
  }
  return breakdown
}

export function truncateId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) + '...' : id
}

export function getPhaseLabel(phase: string): string {
  const map: Record<string, string> = {
    waiting: 'Waiting',
    preflop: 'Pre-Flop',
    flop: 'Flop',
    turn: 'Turn',
    river: 'River',
    showdown: 'Showdown',
    between_hands: 'Between Hands',
  }
  return map[phase] ?? phase
}
