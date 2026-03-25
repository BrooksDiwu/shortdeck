import { motion, AnimatePresence } from 'framer-motion'
import type { PendingSitRequest } from '@/types'

interface HostApprovalBannerProps {
  requests: PendingSitRequest[]
  onApprove: (sessionId: string) => void
  onReject: (sessionId: string) => void
}

export default function HostApprovalBanner({ requests, onApprove, onReject }: HostApprovalBannerProps) {
  if (requests.length === 0) return null

  const req = requests[0]

  return (
    <AnimatePresence>
      <motion.div
        key={req.session_id}
        initial={{ y: -60, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: -60, opacity: 0 }}
        className="fixed top-14 left-0 right-0 z-40 flex justify-center px-4 pointer-events-none"
        style={{ marginTop: 4 }}
      >
        <div className="bg-zinc-900/95 backdrop-blur border border-zinc-600 rounded-xl px-4 py-3 flex items-center gap-3 pointer-events-auto shadow-lg max-w-sm w-full">
          <div className="flex-1 min-w-0">
            <p className="text-white text-sm font-semibold truncate">
              {req.name ?? req.session_id.slice(0, 8)} wants to sit
            </p>
            <p className="text-zinc-400 text-xs">
              Seat {req.seat} • {req.chips.toLocaleString()} chips
              {requests.length > 1 && ` (+${requests.length - 1} more)`}
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <button
              onClick={() => onReject(req.session_id)}
              className="px-3 py-1.5 bg-red-600/20 hover:bg-red-600/40 border border-red-600/40 text-red-400 text-xs font-semibold rounded-lg transition-colors"
            >
              Reject
            </button>
            <button
              onClick={() => onApprove(req.session_id)}
              className="px-3 py-1.5 bg-green-600/20 hover:bg-green-600/40 border border-green-600/40 text-green-400 text-xs font-semibold rounded-lg transition-colors"
            >
              Approve
            </button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
