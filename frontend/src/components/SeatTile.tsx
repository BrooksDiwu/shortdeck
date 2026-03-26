import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Player, Card } from '@/types'
import { AnimatedCard, FlipCard } from './CardFace'
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
  holeCards?: Card[]
  isWinner?: boolean
  handLabel?: string
  highlightedCardIndices?: number[]
  onSitDown?: () => void
  onRevealCard?: (index: 0 | 1) => void
  onContextMenu?: (e: React.MouseEvent) => void
  isPendingApproval?: boolean
  compact?: boolean
}

function getInitials(name: string): string {
  return name.trim().slice(0, 2).toUpperCase()
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
  compact = false,
}: SeatTileProps) {
  const [revealConfirm, setRevealConfirm] = useState<0 | 1 | null>(null)
  const timerProgress = timerRemaining !== undefined ? timerRemaining / timerSeconds : 1
  const AVATAR_SIZE = isLocal ? 52 : compact ? 44 : 48
  const STROKE = 3
  const R = (AVATAR_SIZE - STROKE * 2) / 2
  const circumference = 2 * Math.PI * R

  // Status colors/labels
  const getStatusInfo = () => {
    if (!player) return null
    if (player.status === 'disconnected') return { label: 'DC', color: 'bg-red-600' }
    if (player.status === 'sitting_out') return { label: 'OUT', color: 'bg-yellow-600' }
    if (player.status === 'folded') return { label: 'FOLD', color: 'bg-zinc-600' }
    if (player.status === 'all_in') return { label: 'ALL IN', color: 'bg-orange-500' }
    return null
  }
  const statusInfo = getStatusInfo()

  // Empty seat
  if (!player) {
    return (
      <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center gap-1">
        {isPendingApproval ? (
          <>
            <div
              className="rounded-full border-2 border-yellow-500/50 bg-zinc-900/80 flex items-center justify-center"
              style={{ width: AVATAR_SIZE, height: AVATAR_SIZE }}
            >
              <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
            </div>
            <span className="text-yellow-400 text-[8px] font-medium">PENDING</span>
          </>
        ) : (
          <>
            <button
              onClick={onSitDown}
              className="rounded-full border-2 border-dashed border-zinc-600 hover:border-green-500 bg-zinc-900/60 hover:bg-zinc-800/60 flex items-center justify-center transition-all group"
              style={{ width: AVATAR_SIZE, height: AVATAR_SIZE }}
              aria-label={`Sit in seat ${seat}`}
            >
              <span className="text-zinc-500 group-hover:text-green-400 text-xs font-semibold transition-colors">SIT</span>
            </button>
            <span className="text-zinc-600 text-[9px]">#{seat}</span>
          </>
        )}
      </motion.div>
    )
  }

  const isFolded = player.status === 'folded'

  return (
    <>
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.8 }}
        className={`flex flex-col items-center gap-0.5 ${isFolded ? 'opacity-50' : ''}`}
        onContextMenu={onContextMenu}
        id={`seat-${seat}`}
      >
        {/* Avatar circle with optional timer arc */}
        <div className="relative" style={{ width: AVATAR_SIZE, height: AVATAR_SIZE }}>
          {/* Timer arc SVG */}
          {timerEnabled && isActing && timerRemaining !== undefined && (
            <svg
              className="absolute inset-0"
              width={AVATAR_SIZE}
              height={AVATAR_SIZE}
              style={{ transform: 'rotate(-90deg)' }}
            >
              <circle
                cx={AVATAR_SIZE / 2}
                cy={AVATAR_SIZE / 2}
                r={R}
                fill="none"
                stroke="#fbbf24"
                strokeWidth={STROKE}
                strokeDasharray={circumference}
                strokeDashoffset={circumference * (1 - timerProgress)}
                strokeLinecap="round"
                opacity={0.85}
              />
            </svg>
          )}

          {/* Avatar background */}
          <div
            className={`
              absolute inset-0 rounded-full flex items-center justify-center select-none
              ${isLocal && isActing ? 'ring-2 ring-yellow-400 ring-offset-2 ring-offset-[#0f2318]' : ''}
              ${isLocal && isWinner ? 'ring-2 ring-yellow-300 shadow-lg shadow-yellow-400/40' : ''}
              ${!isLocal && isActing ? 'ring-2 ring-yellow-400 ring-offset-1 ring-offset-transparent' : ''}
              ${!isLocal && isWinner ? 'ring-2 ring-yellow-300 shadow-lg shadow-yellow-400/40' : ''}
              ${isLocal ? 'bg-[#2a4a35]' : 'bg-[#1e3828]'}
            `}
          >
            <span
              className={`font-bold text-white tracking-wide ${
                isLocal ? 'text-base' : compact ? 'text-xs' : 'text-sm'
              }`}
            >
              {getInitials(player.name)}
            </span>
          </div>

          {/* Dealer button */}
          {isDealer && (
            <div className="absolute -top-1 -left-1 w-4 h-4 rounded-full bg-white text-black text-[8px] font-bold flex items-center justify-center shadow-md z-10 border border-zinc-300">
              D
            </div>
          )}

          {/* Status badge */}
          {statusInfo && (
            <div className={`absolute -top-1 -right-1 ${statusInfo.color} text-white text-[7px] px-1 py-0.5 rounded-full font-bold z-10 leading-none`}>
              {statusInfo.label}
            </div>
          )}

          {/* Admin/HOST badge */}
          {player.is_admin && (
            <div className="absolute -bottom-1 -left-1 bg-amber-500 text-black text-[7px] px-1 rounded-full font-bold z-10 leading-none py-0.5">
              HOST
            </div>
          )}
        </div>

        {/* Name */}
        <span
          className={`text-white font-medium leading-none text-center truncate max-w-[64px] ${
            compact ? 'text-[9px]' : isLocal ? 'text-[11px]' : 'text-[10px]'
          }`}
        >
          {player.name}{isLocal ? ' ✦' : ''}
        </span>

        {/* Stack */}
        <span className={`text-yellow-400 font-mono leading-none ${compact ? 'text-[9px]' : 'text-[10px]'}`}>
          {formatAmount(player.stack, denomination)}
        </span>

        {/* Opponent card back indicators */}
        {!isLocal && compact && !isFolded && (player.hole_cards.length > 0 || player.status === 'active' || player.status === 'all_in') && (
          <div className="flex gap-0.5 mt-0.5">
            {[0, 1].map((i) => (
              <div
                key={i}
                className="w-4 h-6 rounded-sm bg-red-800/70 border border-red-700/50 flex items-center justify-center"
              >
                <span className="text-[5px] text-red-300/60 font-bold">?</span>
              </div>
            ))}
          </div>
        )}

        {/* Hole cards — only for local player */}
        {isLocal && (() => {
          const cards = holeCards && holeCards.length > 0 ? holeCards : player.hole_cards
          const isRevealed = player.is_revealed ?? [false, false]
          if (cards.length === 0) return null
          return (
            <div className="flex gap-1 mt-2">
              {cards.map((card, i) => {
                const highlighted = highlightedCardIndices.includes(i)
                return (
                  <div key={i} className="relative">
                    <AnimatedCard
                      card={card}
                      faceDown={false}
                      size="lg"
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
              })}
            </div>
          )
        })()}

        {/* For opponent revealed cards at showdown */}
        {!isLocal && player.hole_cards.length > 0 && (player.is_revealed ?? [false, false]).some(Boolean) && (
          <div className="flex gap-0.5 mt-0.5">
            {player.hole_cards.map((card, i) => (
              <FlipCard
                key={i}
                card={card}
                faceUp={(player.is_revealed ?? [false, false])[i]}
                size="sm"
                highlighted={highlightedCardIndices.includes(i)}
              />
            ))}
          </div>
        )}

        {/* Winner hand label */}
        {handLabel && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-0.5 bg-yellow-500/20 border border-yellow-500/40 rounded px-1 py-0.5"
          >
            <span className="text-yellow-300 text-[8px] font-medium">{handLabel}</span>
          </motion.div>
        )}
      </motion.div>

      {/* Reveal card confirmation modal */}
      <Modal open={revealConfirm !== null} onClose={() => setRevealConfirm(null)} title="Reveal Card?">
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
