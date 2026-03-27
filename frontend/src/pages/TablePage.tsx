import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useSessionStore } from '@/stores/sessionStore'
import { useGameStore } from '@/stores/gameStore'
import { useChipAnimations } from '@/hooks/useChipAnimations'
import PokerTable from '@/components/poker/PokerTable'
import VoteBanner from '@/components/VoteBanner'
import PauseBanner from '@/components/PauseBanner'
import OptionsDrawer from '@/components/OptionsDrawer'
import SitDownModal from '@/components/SitDownModal'
import HostApprovalBanner from '@/components/HostApprovalBanner'
import ConnectionStatus from '@/components/ConnectionStatus'

export default function TablePage() {
  const { id: tableId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { token, sessionId, clearSession } = useSessionStore()
  const {
    connect,
    disconnect,
    sendMessage,
    table,
    connectionState,
    connectionError,
    holeCards,
    voteResolution,
    localPlayerId,
  } = useGameStore()

  // GSAP chip animations
  useChipAnimations()

  const [menuOpen, setMenuOpen] = useState(false)
  const [sitSeat, setSitSeat] = useState<number | null>(null)
  const [sitDownOpen, setSitDownOpen] = useState(false)
  const [contextMenuSeat, setContextMenuSeat] = useState<{ seat: number; x: number; y: number } | null>(null)
  const [pendingSitOut, setPendingSitOut] = useState(false)

  // When hand ends, auto-send queued sit-out
  useEffect(() => {
    if (!pendingSitOut) return
    if (!table) return
    if (table.phase === 'between_hands' || table.phase === 'waiting') {
      sendMessage({ type: 'sit_out' })
      setPendingSitOut(false)
    }
  }, [table?.phase, pendingSitOut, sendMessage])

  // Clear pending sit-out if player is already sitting out (e.g. reconnect)
  const localPlayerStatus = table && localPlayerId
    ? Object.values(table.players).find((p) => p.session_id === localPlayerId)?.status
    : undefined
  useEffect(() => {
    if (localPlayerStatus === 'sitting_out') setPendingSitOut(false)
  }, [localPlayerStatus])

  // Auto-connect on mount if session exists
  useEffect(() => {
    if (!tableId) return

    const doConnect = async () => {
      const currentToken = token
      const currentSessionId = sessionId

      // If no session, redirect to lobby (they need a name)
      if (!currentToken || !currentSessionId) {
        navigate('/')
        return
      }

      connect(tableId, currentToken, currentSessionId)
    }

    void doConnect()

    return () => {
      disconnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tableId])

  // Redirect to lobby with error message when rejected (e.g. duplicate name)
  useEffect(() => {
    if (connectionError) {
      clearSession()
      navigate('/', { state: { error: connectionError } })
    }
  }, [connectionError, navigate, clearSession])

  const localPlayer = table && localPlayerId
    ? Object.values(table.players).find((p) => p.session_id === localPlayerId) ?? null
    : null

  const isAdmin = localPlayer?.is_admin ?? false
  const isSeated = localPlayer !== null

  // Debug logging
  console.log('[TablePage] isAdmin:', isAdmin, 'localPlayerId:', localPlayerId, 'pending_sit_requests:', table?.pending_sit_requests)

  const handleSitDown = (seat: number) => {
    setSitSeat(seat)
    setSitDownOpen(true)
  }

  const handleSitDownConfirm = (seat: number, chips: number) => {
    sendMessage({ type: 'sit_down_request', seat, chips })
  }

  const handleVote = (direction: 'for' | 'against') => {
    sendMessage({ type: 'vote', vote: direction })
  }

  // Dismiss context menu
  useEffect(() => {
    if (!contextMenuSeat) return
    const handler = () => setContextMenuSeat(null)
    window.addEventListener('click', handler)
    return () => window.removeEventListener('click', handler)
  }, [contextMenuSeat])

  if (connectionState === 'connecting' || (!table && connectionState === 'connected')) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border-2 border-green-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-zinc-400 text-sm">Connecting to table...</p>
        </div>
      </div>
    )
  }

  if (connectionState === 'error') {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 text-lg font-semibold mb-2">Connection Failed</p>
          <p className="text-zinc-500 text-sm mb-4">
            {connectionError ?? 'Could not connect to the table.'}
          </p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-white text-sm"
          >
            Return to Lobby
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col overflow-hidden">
      {/* Banners float above the table */}
      {table && (
        <div className="fixed top-0 left-0 right-0 z-50 flex flex-col pointer-events-none">
          <div className="pointer-events-auto">
            <VoteBanner
              vote={table.pending_vote}
              resolution={voteResolution}
              localPlayerId={localPlayerId}
              onVote={handleVote}
            />
            <PauseBanner table={table} />
            {isAdmin && table.pending_sit_requests.length > 0 && (
              <HostApprovalBanner
                requests={table.pending_sit_requests}
                onApprove={(sid) => sendMessage({ type: 'approve_sit_down', session_id: sid })}
                onReject={(sid) => sendMessage({ type: 'reject_sit_down', session_id: sid })}
              />
            )}
          </div>
        </div>
      )}

      {/* Mobile poker table — fills full screen */}
      {table ? (
        <PokerTable
          table={table}
          localPlayerId={localPlayerId}
          holeCards={holeCards}
          onMenuOpen={() => setMenuOpen(true)}
          onSitDown={handleSitDown}
          onStartHand={() => sendMessage({ type: 'start_hand' })}
          pendingSitOut={pendingSitOut}
        />
      ) : (
        <div className="flex items-center justify-center h-[100dvh]">
          <p className="text-zinc-600 text-sm">Waiting for table state...</p>
        </div>
      )}

      {/* Options drawer */}
      <OptionsDrawer
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        table={table}
        localPlayerId={localPlayerId}
        isSeated={isSeated}
        isAdmin={isAdmin}
        pendingSitOut={pendingSitOut}
        onRequestSitOut={() => setPendingSitOut(true)}
        onCancelSitOut={() => setPendingSitOut(false)}
      />

      {/* Sit down modal */}
      <SitDownModal
        open={sitDownOpen}
        seat={sitSeat}
        onConfirm={handleSitDownConfirm}
        onClose={() => setSitDownOpen(false)}
      />

      {/* Context menu for host */}
      <AnimatePresence>
        {contextMenuSeat && isAdmin && table && (
          <HostContextMenu
            seat={contextMenuSeat.seat}
            x={contextMenuSeat.x}
            y={contextMenuSeat.y}
            table={table}
            onClose={() => setContextMenuSeat(null)}
          />
        )}
      </AnimatePresence>

      {/* Connection status indicator */}
      <ConnectionStatus state={connectionState} />
    </div>
  )
}


function HostContextMenu({
  seat,
  x,
  y,
  table,
  onClose,
}: {
  seat: number
  x: number
  y: number
  table: import('@/types').Table
  onClose: () => void
}) {
  const sendMessage = useGameStore((s) => s.sendMessage)
  const player = Object.values(table.players).find((p) => p.seat === seat)

  if (!player) return null

  const menuItems = [
    {
      label: 'Stand Up Player',
      onClick: () => sendMessage({ type: 'host_stand_up', session_id: player.session_id }),
    },
    {
      label: 'Remove Player',
      danger: true,
      onClick: () => {
        if (confirm(`Remove ${player.name} from table?`)) {
          sendMessage({ type: 'host_remove_player', session_id: player.session_id })
        }
      },
    },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="fixed z-50 bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl overflow-hidden w-48"
      style={{ left: Math.min(x, window.innerWidth - 200), top: Math.min(y, window.innerHeight - 120) }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="px-3 py-2 border-b border-zinc-800">
        <p className="text-white text-sm font-semibold truncate">{player.name}</p>
        <p className="text-zinc-500 text-xs">Seat {seat}</p>
      </div>
      {menuItems.map((item) => (
        <button
          key={item.label}
          onClick={() => { item.onClick(); onClose() }}
          className={`w-full text-left px-3 py-2 text-sm hover:bg-zinc-800 transition-colors ${
            item.danger ? 'text-red-400' : 'text-zinc-200'
          }`}
        >
          {item.label}
        </button>
      ))}
    </motion.div>
  )
}
