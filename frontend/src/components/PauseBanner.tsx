import { motion, AnimatePresence } from 'framer-motion'
import type { Table } from '@/types'
import { useGameStore } from '@/stores/gameStore'

interface PauseBannerProps {
  table: Table
}

export default function PauseBanner({ table }: PauseBannerProps) {
  const sendMessage = useGameStore((s) => s.sendMessage)

  if (!table.is_paused && !table.pause_requested_by) return null

  const requester = table.pause_requested_by
    ? Object.values(table.players).find((p) => p.session_id === table.pause_requested_by)?.name ??
      table.pause_requested_by.slice(0, 8)
    : null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: -60, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: -60, opacity: 0 }}
        className="fixed top-14 left-0 right-0 z-40 flex justify-center px-4 pointer-events-none"
      >
        <div className="bg-yellow-900/90 backdrop-blur border border-yellow-700/50 rounded-xl px-4 py-2.5 flex items-center gap-3 pointer-events-auto shadow-lg">
          <svg className="w-4 h-4 text-yellow-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-yellow-200 text-sm">
            {table.is_paused
              ? `Game paused${requester ? ` by ${requester}` : ''}`
              : `Game will pause before next hand${requester ? ` (requested by ${requester})` : ''}`}
          </span>
          <button
            onClick={() => sendMessage({ type: 'unpause_request' })}
            className="ml-2 px-3 py-1 bg-yellow-600 hover:bg-yellow-500 rounded-lg text-white text-xs font-semibold transition-colors shrink-0"
          >
            Unpause
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
