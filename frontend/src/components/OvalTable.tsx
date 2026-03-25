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

  const totalSeats = table.rules.max_players
  const isTall = dimensions.h > dimensions.w  // portrait / mobile

  const playerBySeat = Object.fromEntries(
    Object.values(table.players).map((p) => [p.seat, p])
  )

  const pendingSeatMap = new Map(
    table.pending_sit_requests.map((r) => [r.seat, r])
  )

  const isHandActive = ['preflop', 'flop', 'turn', 'river', 'showdown'].includes(table.phase)

  const winnerSeats: Set<number> = new Set()
  if (table.phase === 'showdown' || table.phase === 'between_hands') {
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

  // ─── Shared seat renderer ──────────────────────────────────────────────────
  const renderSeat = (seatIndex: number, compact = false) => {
    const player = playerBySeat[seatIndex] ?? null
    const pending = pendingSeatMap.get(seatIndex)
    const isActing = isHandActive && seatIndex === table.current_action_seat
    return (
      <SeatWithTimer
        key={seatIndex}
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
        compact={compact}
      />
    )
  }

  // ─── Board / center content (shared between both layouts) ──────────────────
  const renderBoard = (size: 'sm' | 'md') => (
    <div className="flex flex-col items-center justify-center gap-1.5 pointer-events-none">
      <div className="flex gap-1 flex-wrap justify-center">
        <AnimatePresence>
          {table.board.primary.map((card, i) => (
            <AnimatedCard key={`primary-${i}`} card={card} faceDown={false} size={size} delay={i * 0.12} />
          ))}
          {rabbitHuntCards.map((card, i) => (
            <AnimatedCard key={`rabbit-${i}`} card={card} faceDown={false} size={size} ghost delay={i * 0.1} />
          ))}
        </AnimatePresence>
      </div>

      {table.board.secondary.length > 0 && (
        <div className="flex gap-1 flex-wrap justify-center">
          <AnimatePresence>
            {table.board.secondary.map((card, i) => (
              <AnimatedCard key={`secondary-${i}`} card={card} faceDown={false} size="sm" delay={i * 0.1} />
            ))}
          </AnimatePresence>
        </div>
      )}

      {table.pot > 0 && (
        <motion.div
          id="pot-display"
          className="flex items-center gap-1.5 bg-black/40 rounded-full px-3 py-1 pointer-events-auto"
          initial={{ scale: 0.8 }}
          animate={{ scale: 1 }}
        >
          <ChipStack amount={table.pot} size="sm" />
          <span className="text-yellow-300 text-xs font-mono font-bold">
            {formatAmount(table.pot, table.rules.denomination)}
          </span>
        </motion.div>
      )}

      {table.side_pots.length > 0 && (
        <div className="flex gap-1.5 flex-wrap justify-center">
          {table.side_pots.map((sp, i) => (
            <div key={i} className="bg-black/30 rounded px-2 py-0.5">
              <span className="text-zinc-300 text-[10px]">
                Side: {formatAmount(sp.amount, table.rules.denomination)}
              </span>
            </div>
          ))}
        </div>
      )}

      {table.phase === 'waiting' && (
        <span className="text-zinc-400 text-xs">Waiting for players...</span>
      )}

      {table.is_paused && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-black/60 rounded-lg px-3 py-1.5 text-center"
        >
          <p className="text-yellow-400 text-xs font-semibold">Game Paused</p>
          <p className="text-zinc-400 text-[10px]">Waiting to resume...</p>
        </motion.div>
      )}

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
  )

  // ─── Mobile portrait layout (tall oval, seats absolutely positioned) ────────
  //
  // All 9 seats are placed around a portrait-aspect-ratio ellipse using the
  // same getSeatPosition() math as desktop, with one key correction:
  //
  //   getSeatPosition uses standard math convention where y increases upward.
  //   CSS y increases downward, so we negate pos.y:
  //     seatCenterY = cy - pos.y
  //
  //   This maps angle 270° (pos.y = -ry) → cy + ry  =  CSS bottom  (local player)
  //              angle  90° (pos.y = +ry) → cy - ry  =  CSS top     (far opponents)
  //
  if (isTall) {
    const W = dimensions.w
    const H = dimensions.h

    // Tile dimensions ————————————————————————————————————————————————————————
    // Compact (non-local) tiles: just name + stack + tiny card stubs
    // Local tile: full size with visible hole cards
    const COMPACT_W = 64
    const COMPACT_H = 72
    const LOCAL_W   = 84
    const LOCAL_H   = 110
    const PAD       = 4   // min gap from any screen edge

    // Derive ring radii from available screen space ——————————————————————————
    //
    // Vertical: local seat bottom = cy + ry + LOCAL_H/2  = H - PAD
    //           far seat top      = cy - ry - COMPACT_H/2 = PAD
    //   → 2*ry = H - 2*PAD - LOCAL_H/2 - COMPACT_H/2
    const ry = (H - 2 * PAD - LOCAL_H / 2 - COMPACT_H / 2) / 2

    // Horizontal: side seats (at 0°/180°) are at ±rx from cx.
    //   rx + COMPACT_W/2 + PAD ≤ W/2  →  rx = W/2 - COMPACT_W/2 - PAD
    const rx = W / 2 - COMPACT_W / 2 - PAD

    // Oval center: derived so local seat (cy + ry) clears the bottom edge.
    //   cy + ry + LOCAL_H/2 = H - PAD  →  cy = H - PAD - LOCAL_H/2 - ry
    const cx = W / 2
    const cy = H - PAD - LOCAL_H / 2 - ry

    // Board info box is centered at the oval center
    const BOARD_W = 220
    const BOARD_H = 160

    return (
      <div
        ref={containerRef}
        className="relative w-full h-full overflow-hidden select-none"
      >
        {/* ── Decorative felt oval (SVG, drawn behind seats) ── */}
        <svg
          className="absolute inset-0 pointer-events-none"
          width={W}
          height={H}
          style={{ zIndex: 0 }}
        >
          <defs>
            <radialGradient id="portrait-felt" cx="50%" cy="50%" r="50%">
              <stop offset="0%"   stopColor="#1e6b30" />
              <stop offset="80%"  stopColor="#155224" />
              <stop offset="100%" stopColor="#0e3c1a" />
            </radialGradient>
          </defs>
          {/* Wooden rail border */}
          <ellipse cx={cx} cy={cy} rx={rx + 11} ry={ry + 11} fill="#4a2007" />
          {/* Felt surface */}
          <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="url(#portrait-felt)" stroke="#267a38" strokeWidth="3" />
          {/* Subtle inner rim highlight */}
          <ellipse cx={cx} cy={cy} rx={rx - 10} ry={ry - 10} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="1.5" />
        </svg>

        {/* ── Seats placed on the ellipse rim ── */}
        {Array.from({ length: totalSeats }, (_, i) => {
          const isLocal = i === localSeatIndex
          const pos = getSeatPosition(i, totalSeats, localSeatIndex, rx, ry)

          const tileW = isLocal ? LOCAL_W : COMPACT_W
          const tileH = isLocal ? LOCAL_H : COMPACT_H

          // Y-axis flip so local player (270° → pos.y = -ry) ends up at the
          // CSS bottom of the screen, not the top.
          const seatCX = cx + pos.x
          const seatCY = cy - pos.y

          return (
            <div
              key={i}
              className="absolute"
              style={{
                left:      seatCX - tileW / 2,
                top:       seatCY - tileH / 2,
                width:     tileW,
                minHeight: tileH,
                zIndex:    isLocal ? 10 : 5,
              }}
            >
              {renderSeat(i, !isLocal)}
            </div>
          )
        })}

        {/* ── Board / pot info centered in the oval ── */}
        <div
          className="absolute"
          style={{
            left:   cx - BOARD_W / 2,
            top:    cy - BOARD_H / 2,
            width:  BOARD_W,
            height: BOARD_H,
            zIndex: 3,
          }}
        >
          {renderBoard('sm')}
        </div>
      </div>
    )
  }

  // ─── Desktop / landscape oval layout ───────────────────────────────────────
  const SEAT_HALF_H = 52
  const SEAT_HALF_W = 42
  const maxRadiusX = Math.min(dimensions.w * 0.35, dimensions.w * 0.5 - SEAT_HALF_W - 8)
  const maxRadiusY = dimensions.h * 0.5 - SEAT_HALF_H - 8
  const radiusX = Math.max(60, maxRadiusX)
  const radiusY = Math.max(60, maxRadiusY)
  const cx = dimensions.w / 2
  const cy = dimensions.h / 2

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
          <div className="flex gap-1.5">
            <AnimatePresence>
              {table.board.primary.map((card, i) => (
                <AnimatedCard key={`primary-${i}`} card={card} faceDown={false} size="md" delay={i * 0.12} />
              ))}
              {rabbitHuntCards.map((card, i) => (
                <AnimatedCard key={`rabbit-${i}`} card={card} faceDown={false} size="md" ghost delay={i * 0.1} />
              ))}
            </AnimatePresence>
          </div>

          {table.board.secondary.length > 0 && (
            <div className="flex gap-1.5">
              <AnimatePresence>
                {table.board.secondary.map((card, i) => (
                  <AnimatedCard key={`secondary-${i}`} card={card} faceDown={false} size="sm" delay={i * 0.1} />
                ))}
              </AnimatePresence>
            </div>
          )}

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

          {table.side_pots.length > 0 && (
            <div className="flex gap-2">
              {table.side_pots.map((sp, i) => (
                <div key={i} className="bg-black/30 rounded px-2 py-0.5">
                  <span className="text-zinc-300 text-[10px]">Side: {formatAmount(sp.amount, table.rules.denomination)}</span>
                </div>
              ))}
            </div>
          )}

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
        const TILE_W = 80
        const TILE_H = 100
        const seatX = cx + pos.x - TILE_W / 2
        const seatY = cy + pos.y - TILE_H / 2

        return (
          <div
            key={seatIndex}
            className="absolute"
            style={{ left: seatX, top: seatY, width: TILE_W, minHeight: TILE_H }}
          >
            {renderSeat(seatIndex)}
          </div>
        )
      })}
    </div>
  )
}

// ─── SeatWithTimer wrapper (hook must be called at top level, not inside map) ─
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
  compact?: boolean
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
