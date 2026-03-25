import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { ModeVote, TableRulesSchema } from '@/types'
import { getGameModeLabel } from '@/utils/gameUtils'
import { useGameStore } from '@/stores/gameStore'

interface VoteBannerProps {
  vote: ModeVote | null
  resolution: { passed: boolean; newRules?: TableRulesSchema } | null
  localPlayerId: string | null
  onVote: (direction: 'for' | 'against') => void
}

export default function VoteBanner({ vote, resolution, localPlayerId, onVote }: VoteBannerProps) {
  const clearVoteResolution = useGameStore((s) => s.clearVoteResolution)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    if (!resolution) {
      setDismissed(false)
      return
    }
    const t = setTimeout(() => {
      setDismissed(true)
      clearVoteResolution()
    }, 5000)
    return () => clearTimeout(t)
  }, [resolution, clearVoteResolution])

  const isVisible = (vote !== null || resolution !== null) && !dismissed

  const hasVoted = localPlayerId
    ? vote?.votes_for.includes(localPlayerId) || vote?.votes_against.includes(localPlayerId)
    : false

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ y: -80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -80, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          className="fixed top-14 left-0 right-0 z-50 flex justify-center px-4 pointer-events-none"
        >
          <div className="bg-zinc-900/95 backdrop-blur border border-zinc-700 rounded-xl shadow-2xl p-4 w-full max-w-md pointer-events-auto">
            {resolution ? (
              // Resolved state
              <div className="text-center">
                <div className={`text-lg font-bold mb-1 ${resolution.passed ? 'text-green-400' : 'text-red-400'}`}>
                  {resolution.passed ? 'Rule Change Approved' : 'Rule Change Rejected'}
                </div>
                {resolution.passed && resolution.newRules && (
                  <p className="text-zinc-300 text-sm">
                    New rules: {getGameModeLabel(resolution.newRules)} {resolution.newRules.small_blind}/{resolution.newRules.big_blind}
                  </p>
                )}
                <p className="text-zinc-500 text-xs mt-1">Takes effect next hand</p>
              </div>
            ) : vote ? (
              // Active vote
              <>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <p className="text-yellow-400 text-sm font-semibold">Rule Change Proposed</p>
                    <p className="text-white text-base font-bold mt-0.5">
                      {getGameModeLabel(vote.proposed_rules)} {vote.proposed_rules.small_blind}/{vote.proposed_rules.big_blind}
                    </p>
                    <div className="flex gap-4 mt-2">
                      <span className="text-green-400 text-sm">
                        For: {vote.votes_for.length}
                      </span>
                      <span className="text-red-400 text-sm">
                        Against: {vote.votes_against.length}
                      </span>
                    </div>
                  </div>

                  {!hasVoted && (
                    <div className="flex flex-col gap-2 shrink-0">
                      <button
                        onClick={() => onVote('for')}
                        className="px-4 py-1.5 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-semibold text-white transition-colors"
                      >
                        Vote For
                      </button>
                      <button
                        onClick={() => onVote('against')}
                        className="px-4 py-1.5 bg-red-600 hover:bg-red-500 rounded-lg text-sm font-semibold text-white transition-colors"
                      >
                        Against
                      </button>
                    </div>
                  )}

                  {hasVoted && (
                    <div className="shrink-0 text-zinc-400 text-sm italic">Voted</div>
                  )}
                </div>

                {/* Progress bar */}
                <div className="mt-3 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-green-500 rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${(vote.votes_for.length / Math.max(1, vote.votes_for.length + vote.votes_against.length)) * 100}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
              </>
            ) : null}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
