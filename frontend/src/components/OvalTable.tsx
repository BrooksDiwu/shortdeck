import { useRef, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { Table, Card } from '@/types'
import { getSeatPosition, formatAmount } from '@/utils/gameUtils'
import { useTimerCountdown } from '@/hooks/useTimerCountdown'
import SeatTile from './SeatTile'
import { AnimatedCard } from './CardFace'
import ChipStack from './ChipStack'

interface OvalTableProps {
  table: Table
  localPlayerId: string | null
  holeCards: Card[]
  rabbitHuntCards: Card[]
  onSitDown: (seat: number) => void
  onRevealCard: (index: 0 | 1) => void
  onRabbitHunt: () => void
  onSeatContextMenu?: (seat: number, e: React.MouseEvent) => void
}

export default function OvalTable({
  table,
  localPlayerId,
  holeCards,
  rabbitHuntCards,
  onSitDown,
  onRevealCard,
  onRabbitHunt,
  onSeatContextMenu,
}: OvalTableProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ w: 600, h: 360 })

  useEffect(() => {
    if (!containerRef.current) return
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        setDimensions({ w: width, h: height })
      }
    })
    ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  // Find local player's seat index
  const localPlayer = localPlayerId
    ? Object.values(table.players).find((p) => p.session_id === localPlayerId) ?? null
    : null
  const localSeatIndex = localPlayer ? localPlayer.seat : 0

  // Build seat slots (0..max_players-1)
  const totalSeats = table.rules.max_players
  const radiusX = dimensions.w * 0.42
  const radiusY = dimensions.h * 0.42
  const cx = dimensions.w / 2
  const cy = dimensions.h / 2

  const playerBySeat = Object.fromEntries(
    Object.values(table.players).map((p) => [p.seat, p])
  )

  const pendingSeatMap = new Map(
    table.pending_sit_requests.map((r) => [r.seat, r])
  )

  const isHandActive = ['preflop', 'flop', 'turn', 'river', 'showdown'].includes(table.phase)

  // Determine winner seats from side_pots or pot (simplified — highlight all_in/active with most chips)
  const winnerSeats: Set<number> = new Set()
  if (table.phase === 'showdown' || table.phase === 'between_hands') {
    // Highlight last active player if only one remains
    const activePlayers = Object.values(table.players).filter(
      (p) => p.status === 'active' || p.status === 'all_in'
    )
    if (activePlayers.length === 1) {
      winnerSeats.add(activePlayers[0].seat)
    }
  }

  const canRabbitHunt =
    rabbitHuntCards.length === 0 &&
    localPlayer &&
    winnerSeats.has(localPlayer.seat) &&
    table.phase === 'between_hands'

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full"
      style={{ minHeight: 300 }}
    >
      {/* Oval felt table */}
      <div
        className="absolute felt-texture rounded-[50%] border-4"
        style={{
          left: cx - radiusX,
          top: cy - radiusY,
          width: radiusX * 2,
          height: radiusY * 2,
          borderColor: 'var(--color-table-rim)',
          boxShadow: '0 0 0 6px #2d1505, 0 8px 40px rgba(0,0,0,0.6)',
        }}
      >
        {/* Inner glow ring */}
        <div
          className="absolute rounded-[50%] pointer-events-none"
          style={{
            inset: 8,
            border: '1px solid rgba(255,255,255,0.05)',
          }}
        />

        {/* Center content: pot + board */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 pointer-events-none">
          {/* Primary board */}
          <div className="flex gap-1.5">
            <AnimatePresence>
              {table.board.primary.map((card, i) => (
                <AnimatedCard
                  key={`primary-${i}`}
                  card={card}
                  faceDown={false}
                  size="md"
                  delay={i * 0.12}
                />
              ))}
              {/* Rabbit hunt ghost cards */}
              {rabbitHuntCards.map((card, i) => (
                <AnimatedCard
                  key={`rabbit-${i}`}
                  card={card}
                  faceDown={false}
                  size="md"
                  ghost
                  delay={i * 0.1}
                />
              ))}
            </AnimatePresence>
          </div>

          {/* Secondary board (extra flop) */}
          {table.board.secondary.length > 0 && (
            <div className="flex gap-1.5">
              <AnimatePresence>
                {table.board.secondary.map((card, i) => (
                  <AnimatedCard
                    key={`secondary-${i}`}
                    card={card}
                    faceDown={false}
                    size="sm"
                    delay={i * 0.1}
                  />
                ))}
              </AnimatePresence>
            </div>
          )}

          {/* Pot */}
          {table.pot > 0 && (
            <motion.div
              id="pot-display"
              className="flex items-center gap-2 bg-black/40 rounded-full px-3 py-1 pointer-events-none"
              initial={{ scale: 0.8 }}
              animate={{ scale: 1 }}
            >
              <ChipStack amount={table.pot} size="sm" />
              <span className="text-yellow-300 text-sm font-mono font-bold">
                {formatAmount(table.pot, table.rules.denomination)}
              </span>
            </motion.div>
          )}

          {/* Side pots */}
          {table.side_pots.length > 0 && (
            <div className="flex gap-2">
              {table.side_pots.map((sp, i) => (
                <div key={i} className="bg-black/30 rounded px-2 py-0.5">
                  <span className="text-zinc-300 text-[10px]">Side: {formatAmount(sp.amount, table.rules.denomination)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Phase label */}
          {table.phase === 'waiting' && (
            <span className="text-zinc-400 text-sm">Waiting for players...</span>
          )}

          {table.is_paused && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="bg-black/60 rounded-lg px-4 py-2 text-center"
            >
              <p className="text-yellow-400 text-sm font-semibold">Game Paused</p>
              <p className="text-zinc-400 text-xs">Waiting to resume...</p>
            </motion.div>
          )}

          {/* Rabbit hunt button */}
          {canRabbitHunt && (
            <motion.button
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              onClick={(e) => { e.stopPropagation(); onRabbitHunt() }}
              className="pointer-events-auto bg-zinc-800/90 hover:bg-zinc-700 border border-zinc-600 text-white text-xs px-3 py-1.5 rounded-lg transition-colors"
            >
              Rabbit Hunt?
            </motion.button>
          )}
        </div>
      </div>

      {/* Seats around the oval */}
      {Array.from({ length: totalSeats }, (_, seatIndex) => {
        const pos = getSeatPosition(seatIndex, totalSeats, localSeatIndex, radiusX, radiusY)
        const player = playerBySeat[seatIndex] ?? null
        const pending = pendingSeatMap.get(seatIndex)
        const TILE_W = 80
        const TILE_H = 100
        const seatX = cx + pos.x - TILE_W / 2
        const seatY = cy + pos.y - TILE_H / 2
        const isActing = isHandActive && seatIndex === table.current_action_seat

        return (
          <div
            key={seatIndex}
            className="absolute"
            style={{ left: seatX, top: seatY, width: TILE_W, minHeight: TILE_H }}
          >
            <SeatWithTimer
              seat={seatIndex}
              player={player}
              isLocal={player?.session_id === localPlayerId}
              isDealer={seatIndex === table.dealer_seat}
              isActing={isActing}
              timerEnabled={table.rules.timer_enabled}
              timerSeconds={table.rules.timer_seconds}
              denomination={table.rules.denomination}
              holeCards={player?.session_id === localPlayerId ? holeCards : undefined}
              isWinner={winnerSeats.has(seatIndex)}
              onSitDown={player ? undefined : () => onSitDown(seatIndex)}
              onRevealCard={player?.session_id === localPlayerId ? onRevealCard : undefined}
              onContextMenu={player && onSeatContextMenu ? (e) => onSeatContextMenu(seatIndex, e) : undefined}
              isPendingApproval={!!pending}
            />
          </div>
        )
      })}
    </div>
  )
}

// Wrapper that runs the timer hook (hooks can't be called inside map())
interface SeatWithTimerProps {
  seat: number
  player: import('@/types').Player | null
  isLocal: boolean
  isDealer: boolean
  isActing: boolean
  timerEnabled: boolean
  timerSeconds: number
  denomination: 'chips' | 'usd'
  holeCards?: import('@/types').Card[]
  isWinner: boolean
  onSitDown?: () => void
  onRevealCard?: (index: 0 | 1) => void
  onContextMenu?: (e: React.MouseEvent) => void
  isPendingApproval: boolean
}

function SeatWithTimer({ isActing, timerEnabled, timerSeconds, ...rest }: SeatWithTimerProps) {
  const timerRemaining = useTimerCountdown(timerSeconds, isActing && timerEnabled)
  return (
    <SeatTile
      {...rest}
      isActing={isActing}
      timerEnabled={timerEnabled}
      timerSeconds={timerSeconds}
      timerRemaining={timerEnabled && isActing ? timerRemaining : undefined}
    />
  )
}
