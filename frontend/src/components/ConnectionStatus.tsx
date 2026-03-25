import { motion, AnimatePresence } from 'framer-motion'

interface ConnectionStatusProps {
  state: 'disconnected' | 'connecting' | 'connected' | 'error'
}

export default function ConnectionStatus({ state }: ConnectionStatusProps) {
  const showBadge = state !== 'connected'

  return (
    <AnimatePresence>
      {showBadge && (
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          className="fixed bottom-4 right-4 z-50"
        >
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium shadow-lg ${
              state === 'connecting'
                ? 'bg-yellow-900/80 border border-yellow-700/50 text-yellow-300'
                : state === 'error'
                ? 'bg-red-900/80 border border-red-700/50 text-red-300'
                : 'bg-zinc-800/80 border border-zinc-700/50 text-zinc-400'
            }`}
          >
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                state === 'connecting'
                  ? 'bg-yellow-400 animate-pulse'
                  : state === 'error'
                  ? 'bg-red-400'
                  : 'bg-zinc-500'
              }`}
            />
            {state === 'connecting' && 'Connecting...'}
            {state === 'disconnected' && 'Disconnected'}
            {state === 'error' && 'Connection Error'}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
