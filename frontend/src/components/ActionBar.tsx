import { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import type { Table, Player } from '@/types'
import { useGameStore } from '@/stores/gameStore'
import { formatAmount } from '@/utils/gameUtils'

interface ActionBarProps {
  table: Table
  localPlayer: Player
  mode: 'bottom' | 'overlay'
}

function computeCallAmount(table: Table, player: Player): number {
  const maxBet = Math.max(...Object.values(table.players).map((p) => p.current_bet))
  return Math.max(0, maxBet - player.current_bet)
}

function computeMinRaise(table: Table): number {
  const maxBet = Math.max(...Object.values(table.players).map((p) => p.current_bet))
  return maxBet * 2
}

function computePotLimit(table: Table, player: Player): number {
  const callAmount = computeCallAmount(table, player)
  const potAfterCall = table.pot + callAmount
  return callAmount + potAfterCall
}

function computeMaxRaise(table: Table, player: Player): number {
  if (table.rules.betting === 'pot_limit') {
    return Math.min(player.stack + player.current_bet, computePotLimit(table, player) + player.current_bet)
  }
  return player.stack + player.current_bet // no-limit: all in
}

function ActionControls({ table, localPlayer }: { table: Table; localPlayer: Player }) {
  const sendMessage = useGameStore((s) => s.sendMessage)
  const [showRaise, setShowRaise] = useState(false)
  const [raiseAmount, setRaiseAmount] = useState(0)

  const callAmount = computeCallAmount(table, localPlayer)
  const canCheck = callAmount === 0
  const minRaise = computeMinRaise(table)
  const maxRaise = computeMaxRaise(table, localPlayer)
  const potLimit = computePotLimit(table, localPlayer)

  const handleAction = useCallback(
    (action: 'fold' | 'check' | 'call' | 'raise' | 'all_in', amount?: number) => {
      sendMessage({ type: 'action', action, amount })
      setShowRaise(false)
    },
    [sendMessage]
  )

  return (
    <div className="flex flex-col gap-2 w-full">
      {showRaise && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="flex flex-col gap-2 bg-zinc-800/80 rounded-lg p-3"
        >
          <div className="flex items-center gap-2">
            <span className="text-zinc-300 text-sm">Raise to:</span>
            <input
              type="number"
              className="flex-1 bg-zinc-700 border border-zinc-600 rounded px-2 py-1 text-white text-sm text-right focus:outline-none focus:border-green-500 min-w-0"
              value={raiseAmount || ''}
              onChange={(e) => {
                const v = Number(e.target.value)
                setRaiseAmount(Math.max(minRaise, Math.min(maxRaise, v)))
              }}
              min={minRaise}
              max={maxRaise}
            />
          </div>

          <input
            type="range"
            className="w-full accent-green-500"
            min={minRaise}
            max={maxRaise}
            step={table.rules.big_blind}
            value={raiseAmount || minRaise}
            onChange={(e) => setRaiseAmount(Number(e.target.value))}
          />

          <div className="flex gap-1 flex-wrap">
            {/* Quick-select amounts */}
            {[minRaise, potLimit, Math.floor(maxRaise / 2), maxRaise].map((v, i) => {
              const labels = ['Min', 'Pot', '½', 'All-in']
              return (
                <button
                  key={i}
                  onClick={() => setRaiseAmount(v)}
                  className="flex-1 py-1 rounded bg-zinc-700 hover:bg-zinc-600 text-xs text-zinc-200 transition-colors min-w-0"
                >
                  {labels[i]}
                  <br />
                  <span className="text-[10px] text-zinc-400">
                    {formatAmount(v, table.rules.denomination)}
                  </span>
                </button>
              )
            })}
          </div>

          <button
            className="w-full py-2 bg-green-600 hover:bg-green-500 rounded-lg font-semibold text-sm transition-colors"
            onClick={() => handleAction('raise', raiseAmount || minRaise)}
          >
            Raise to {formatAmount(raiseAmount || minRaise, table.rules.denomination)}
          </button>
        </motion.div>
      )}

      <div className="flex gap-2">
        <button
          className="flex-1 py-3 bg-red-600 hover:bg-red-500 rounded-xl font-semibold text-sm transition-colors"
          onClick={() => handleAction('fold')}
        >
          Fold
        </button>

        <button
          className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-semibold text-sm transition-colors"
          onClick={() => handleAction(canCheck ? 'check' : 'call')}
        >
          {canCheck ? 'Check' : `Call ${formatAmount(callAmount, table.rules.denomination)}`}
        </button>

        <button
          className={`flex-1 py-3 rounded-xl font-semibold text-sm transition-colors ${
            showRaise
              ? 'bg-yellow-600 hover:bg-yellow-500'
              : 'bg-green-700 hover:bg-green-600'
          }`}
          onClick={() => {
            setShowRaise(!showRaise)
            if (!showRaise) setRaiseAmount(minRaise)
          }}
        >
          {localPlayer.stack <= callAmount ? 'All-in' : showRaise ? 'Cancel' : 'Raise'}
        </button>
      </div>
    </div>
  )
}

export function BottomActionBar({ table, localPlayer }: Omit<ActionBarProps, 'mode'>) {
  const isActing = table.current_action_seat === localPlayer.seat
  const isHandActive = ['preflop', 'flop', 'turn', 'river'].includes(table.phase)

  if (!isActing || !isHandActive) return null

  return (
    <motion.div
      initial={{ y: 100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 100, opacity: 0 }}
      className="fixed bottom-0 left-0 right-0 z-40 bg-zinc-950/95 backdrop-blur-sm border-t border-zinc-700 px-4 py-3 pb-safe"
    >
      <div className="max-w-lg mx-auto">
        <div className="flex items-center justify-between mb-2">
          <span className="text-yellow-400 text-sm font-semibold">Your Turn</span>
          <span className="text-zinc-400 text-xs">
            Stack: {formatAmount(localPlayer.stack, table.rules.denomination)}
          </span>
        </div>
        <ActionControls table={table} localPlayer={localPlayer} />
      </div>
    </motion.div>
  )
}

export function OverlayActionBar({ table, localPlayer }: Omit<ActionBarProps, 'mode'>) {
  const isActing = table.current_action_seat === localPlayer.seat
  const isHandActive = ['preflop', 'flop', 'turn', 'river'].includes(table.phase)

  if (!isActing || !isHandActive) return null

  // Find seat DOM element to anchor near
  const seatEl = document.getElementById(`seat-${localPlayer.seat}`)
  const rect = seatEl?.getBoundingClientRect()

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className="fixed z-40 w-72"
      style={
        rect
          ? { bottom: window.innerHeight - rect.top + 8, left: rect.left + rect.width / 2 - 144 }
          : { bottom: 100, left: '50%', transform: 'translateX(-50%)' }
      }
    >
      <div className="bg-zinc-900/95 backdrop-blur border border-zinc-700 rounded-xl p-3 shadow-2xl">
        <div className="flex items-center justify-between mb-2">
          <span className="text-yellow-400 text-xs font-semibold">Your Turn</span>
        </div>
        <ActionControls table={table} localPlayer={localPlayer} />
      </div>
    </motion.div>
  )
}
