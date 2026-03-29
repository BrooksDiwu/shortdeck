import { X } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"
import type { Table, LeaderboardEntry } from "@/types"
import { formatAmount } from "@/utils/gameUtils"

interface LeaderboardModalProps {
  open: boolean
  onClose: () => void
  table: Table
}

interface Row {
  session_id: string
  name: string
  buy_in: number
  stack: number
  profit: number
  isActive: boolean
}

const LeaderboardModal = ({ open, onClose, table }: LeaderboardModalProps) => {
  const denom = table.rules.denomination

  // Build rows from active players
  const activeRows: Row[] = Object.values(table.players).map((p) => ({
    session_id: p.session_id,
    name: p.name,
    buy_in: p.buy_in,
    stack: p.stack,
    profit: p.stack - p.buy_in,
    isActive: true,
  }))

  // Build rows from stood-up players (leaderboard)
  const stoodUpRows: Row[] = (table.leaderboard ?? []).map((entry: LeaderboardEntry) => ({
    session_id: entry.session_id,
    name: entry.name,
    buy_in: entry.buy_in,
    stack: entry.final_stack,
    profit: entry.final_stack - entry.buy_in,
    isActive: false,
  }))

  // Sort: active first (by name), then stood-up (by name)
  const rows: Row[] = [
    ...activeRows.sort((a, b) => a.name.localeCompare(b.name)),
    ...stoodUpRows.sort((a, b) => a.name.localeCompare(b.name)),
  ]

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 z-40"
            onClick={onClose}
          />
          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-x-4 top-[10%] z-50 bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl overflow-hidden max-w-lg mx-auto"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
              <h2 className="text-white font-bold text-base">Leaderboard</h2>
              <button onClick={onClose} aria-label="Close">
                <X className="w-5 h-5 text-zinc-400 hover:text-white" />
              </button>
            </div>

            {/* Table */}
            <div className="overflow-y-auto max-h-[60vh]">
              {rows.length === 0 ? (
                <p className="text-zinc-500 text-sm text-center py-8">No players yet</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-zinc-500 text-xs uppercase border-b border-zinc-800">
                      <th className="px-4 py-2 text-left font-medium">Player</th>
                      <th className="px-4 py-2 text-right font-medium">Buy-in</th>
                      <th className="px-4 py-2 text-right font-medium">Stack</th>
                      <th className="px-4 py-2 text-right font-medium">+/–</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => {
                      const profitColor =
                        row.profit > 0
                          ? "text-emerald-400"
                          : row.profit < 0
                          ? "text-red-400"
                          : "text-zinc-400"
                      return (
                        <tr
                          key={`${row.session_id}-${i}`}
                          className={`border-b border-zinc-800/60 ${
                            row.isActive ? "" : "opacity-50"
                          }`}
                        >
                          <td className="px-4 py-2.5 text-left">
                            <div className="flex items-center gap-2">
                              <span className="text-white font-medium truncate max-w-[120px]">
                                {row.name}
                              </span>
                              {!row.isActive && (
                                <span className="text-[10px] bg-zinc-700 text-zinc-400 rounded px-1 py-0.5 shrink-0">
                                  left
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-2.5 text-right text-zinc-400">
                            {formatAmount(row.buy_in, denom)}
                          </td>
                          <td className="px-4 py-2.5 text-right text-zinc-200">
                            {formatAmount(row.stack, denom)}
                          </td>
                          <td className={`px-4 py-2.5 text-right font-semibold ${profitColor}`}>
                            {row.profit >= 0 ? "+" : ""}
                            {formatAmount(row.profit, denom)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

export default LeaderboardModal
