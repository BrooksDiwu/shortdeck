import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Player, Card } from '@/types'
import { AnimatedCard, FlipCard } from './CardFace'
import ChipStack from './ChipStack'
import { formatAmount } from '@/utils/gameUtils'
import Modal from './Modal'

interface SeatTileProps {
  seat: number
  player: Player | null
  isLocal: boolean
  isDealer: boolean
  isActing: boolean
  timerEnabled: boolean
  timerSeconds: number
  timerRemaining?: number
  denomination: 'chips' | 'usd'
  holeCards?: Card[] // local player's revealed hole cards
  isWinner?: boolean
  handLabel?: string
  highlightedCardIndices?: number[]
  onSitDown?: () => void
  onRevealCard?: (index: 0 | 1) => void
  onContextMenu?: (e: React.MouseEvent) => void
  isPendingApproval?: boolean
}

export default function SeatTile({
  seat,
  player,
  isLocal,
  isDealer,
  isActing,
  timerEnabled,
  timerSeconds,
  timerRemaining,
  denomination,
  holeCards,
  isWinner,
  handLabel,
  highlightedCardIndices = [],
  onSitDown,
  onRevealCard,
  onContextMenu,
  isPendingApproval,
}: SeatTileProps) {
  const [revealConfirm, setRevealConfirm] = useState<0 | 1 | null>(null)
  const timerProgress = timerRemaining !== undefined ? timerRemaining / timerSeconds : 1
  const circumference = 2 * Math.PI * 28

  const getStatusBadge = () => {
    if (!player) return null
    if (player.status === 'disconnected') {
      return <span className="absolute -top-1 -right-1 bg-red-600 text-white text-[9px] px-1 rounded-full">DC</span>
    }
    if (player.status === 'sitting_out') {
      return <span className="absolute -top-1 -right-1 bg-yellow-600 text-white text-[9px] px-1 rounded-full">OUT</span>
    }
    if (player.status === 'folded') {
      return <span className="absolute -top-1 -right-1 bg-zinc-600 text-white text-[9px] px-1 rounded-full">FOLD</span>
    }
    if (player.status === 'all_in') {
      return <span className="absolute -top-1 -right-1 bg-orange-500 text-white text-[9px] px-1 rounded-full">ALL IN</span>
    }
    return null
  }

  const renderHoleCards = () => {
    if (!player) return null

    // Empty state
    if (player.hole_cards.length === 0 && !(isLocal && holeCards && holeCards.length > 0)) {
      return (
        <div className="flex gap-0.5 mt-1">
          {[0, 1].map((i) => (
            <div key={i} className="w-7 h-10 rounded bg-zinc-700 border border-zinc-600 opacity-30" />
          ))}
        </div>
      )
    }

    const cards = isLocal && holeCards && holeCards.length > 0 ? holeCards : player.hole_cards
    const isRevealed = player.is_revealed ?? [false, false]

    return (
      <div className="flex gap-0.5 mt-1">
        {cards.map((card, i) => {
          const revealed = isRevealed[i] || isLocal
          const highlighted = highlightedCardIndices.includes(i)

          if (isLocal) {
            return (
              <div key={i} className="relative">
                <AnimatedCard
                  card={card}
                  faceDown={false}
                  size="sm"
                  highlighted={highlighted}
                  delay={i * 0.1}
                  onClick={!isRevealed[i] ? () => setRevealConfirm(i as 0 | 1) : undefined}
                  className={!isRevealed[i] ? 'ring-1 ring-blue-400/50 hover:ring-blue-300 transition-shadow' : ''}
                />
                {!isRevealed[i] && (
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <svg className="w-3 h-3 text-blue-300 opacity-70" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                      <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  </div>
                )}
              </div>
            )
          }

          return (
            <FlipCard
              key={i}
              card={card}
              faceUp={revealed}
              size="sm"
              highlighted={highlighted}
            />
          )
        })}
      </div>
    )
  }

  // Empty seat
  if (!player) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative"
      >
        {isPendingApproval ? (
          <div className="w-20 min-h-[64px] rounded-xl border-2 border-yellow-500/50 bg-zinc-900/80 flex flex-col items-center justify-center p-2 gap-1">
            <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
            <span className="text-yellow-400 text-[9px] font-medium">PENDING</span>
          </div>
        ) : (
          <button
            onClick={onSitDown}
            className="w-20 min-h-[64px] rounded-xl border-2 border-dashed border-zinc-600 hover:border-green-500 bg-zinc-900/60 hover:bg-zinc-800/60 flex flex-col items-center justify-center p-2 gap-1 transition-all group"
            aria-label={`Sit in seat ${seat}`}
          >
            <span className="text-zinc-500 group-hover:text-green-400 text-xs font-semibold transition-colors">SIT</span>
            <span className="text-zinc-600 text-[10px]">#{seat}</span>
          </button>
        )}
      </motion.div>
    )
  }

  return (
    <>
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.8 }}
        className={`
          relative w-20 rounded-xl border-2 p-2 flex flex-col items-center gap-0.5
          ${isActing ? 'thinking-pulse border-yellow-400 bg-zinc-800' : 'border-zinc-700 bg-zinc-900/80'}
          ${isWinner ? 'win-glow border-yellow-400' : ''}
          ${player.status === 'folded' ? 'opacity-50' : ''}
          no-select
        `}
        onContextMenu={onContextMenu}
        id={`seat-${seat}`}
      >
        {/* Timer arc */}
        {timerEnabled && isActing && timerRemaining !== undefined && (
          <svg className="absolute inset-0 w-full h-full" style={{ transform: 'rotate(-90deg)' }}>
            <rect
              x="0" y="0" width="100%" height="100%"
              rx="10" ry="10"
              fill="none"
              stroke="#fbbf24"
              strokeWidth="2"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - timerProgress)}
              className="timer-arc"
              opacity="0.7"
            />
          </svg>
        )}

        {/* Dealer button */}
        {isDealer && (
          <div className="absolute -top-2 -left-2 w-5 h-5 rounded-full bg-white text-black text-[9px] font-bold flex items-center justify-center shadow-lg z-10">
            D
          </div>
        )}

        {/* Status badge */}
        {getStatusBadge()}

        {/* Admin badge */}
        {player.is_admin && (
          <span className="absolute -bottom-1 -left-1 bg-amber-500 text-black text-[8px] px-1 rounded-full font-bold">
            HOST
          </span>
        )}

        {/* Name */}
        <span className="text-white text-[10px] font-semibold w-full text-center truncate leading-none">
          {player.name}
          {isLocal && ' ✦'}
        </span>

        {/* Stack */}
        <span className="text-green-400 text-[11px] font-mono leading-none">
          {formatAmount(player.stack, denomination)}
        </span>

        {/* Hole cards */}
        {renderHoleCards()}

        {/* Current bet */}
        {player.current_bet > 0 && (
          <div className="mt-1 flex items-center gap-1">
            <ChipStack amount={player.current_bet} size="sm" />
            <span className="text-yellow-300 text-[10px] font-mono">
              {formatAmount(player.current_bet, denomination)}
            </span>
          </div>
        )}

        {/* Winner hand label */}
        {handLabel && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-1 bg-yellow-500/20 border border-yellow-500/40 rounded px-1 py-0.5"
          >
            <span className="text-yellow-300 text-[9px] font-medium">{handLabel}</span>
          </motion.div>
        )}
      </motion.div>

      {/* Reveal card confirmation modal */}
      <Modal
        open={revealConfirm !== null}
        onClose={() => setRevealConfirm(null)}
        title="Reveal Card?"
      >
        <p className="text-zinc-300 text-sm mb-4">
          This will show card #{(revealConfirm ?? 0) + 1} to all players. This cannot be undone.
        </p>
        <div className="flex gap-3">
          <button
            className="flex-1 py-2 rounded-lg bg-zinc-700 hover:bg-zinc-600 text-white text-sm transition-colors"
            onClick={() => setRevealConfirm(null)}
          >
            Cancel
          </button>
          <button
            className="flex-1 py-2 rounded-lg bg-yellow-500 hover:bg-yellow-400 text-black font-semibold text-sm transition-colors"
            onClick={() => {
              if (revealConfirm !== null) onRevealCard?.(revealConfirm)
              setRevealConfirm(null)
            }}
          >
            Reveal
          </button>
        </div>
      </Modal>
    </>
  )
}
