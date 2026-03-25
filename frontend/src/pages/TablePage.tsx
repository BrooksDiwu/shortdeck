import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useSessionStore } from '@/stores/sessionStore'
import { useGameStore } from '@/stores/gameStore'
import { useChipAnimations } from '@/hooks/useChipAnimations'
import TopBar from '@/components/TopBar'
import OvalTable from '@/components/OvalTable'
import { BottomActionBar, OverlayActionBar } from '@/components/ActionBar'
import VoteBanner from '@/components/VoteBanner'
import PauseBanner from '@/components/PauseBanner'
import OptionsDrawer from '@/components/OptionsDrawer'
import SitDownModal from '@/components/SitDownModal'
import HostApprovalBanner from '@/components/HostApprovalBanner'
import ConnectionStatus from '@/components/ConnectionStatus'

export default function TablePage() {
  const { id: tableId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { token, sessionId } = useSessionStore()
  const {
    connect,
    disconnect,
    sendMessage,
    table,
    connectionState,
    holeCards,
    rabbitHuntCards,
    actionBarMode,
    voteResolution,
    localPlayerId,
  } = useGameStore()

  // GSAP chip animations
  useChipAnimations()

  const [menuOpen, setMenuOpen] = useState(false)
  const [sitSeat, setSitSeat] = useState<number | null>(null)
  const [sitDownOpen, setSitDownOpen] = useState(false)
  const [contextMenuSeat, setContextMenuSeat] = useState<{ seat: number; x: number; y: number } | null>(null)

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

  const localPlayer = table && localPlayerId
    ? Object.values(table.players).find((p) => p.session_id === localPlayerId) ?? null
    : null

  const isAdmin = localPlayer?.is_admin ?? false
  const isSeated = localPlayer !== null

  const handleSitDown = (seat: number) => {
    setSitSeat(seat)
    setSitDownOpen(true)
  }

  const handleSitDownConfirm = (seat: number, chips: number) => {
    sendMessage({ type: 'sit_down_request', seat, chips })
  }

  const handleRevealCard = (index: 0 | 1) => {
    sendMessage({ type: 'reveal_card', card_index: index })
  }

  const handleRabbitHunt = () => {
    sendMessage({ type: 'rabbit_hunt_request' })
  }

  const handleVote = (direction: 'for' | 'against') => {
    sendMessage({ type: 'vote', vote: direction })
  }

  const handleSeatContextMenu = (seat: number, e: React.MouseEvent) => {
    e.preventDefault()
    setContextMenuSeat({ seat, x: e.clientX, y: e.clientY })
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
          <p className="text-zinc-500 text-sm mb-4">Could not connect to the table.</p>
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
      {/* Top bar */}
      <TopBar table={table} onMenuOpen={() => setMenuOpen(true)} />

      {/* Banners (rendered below topbar) */}
      {table && (
        <>
          <VoteBanner
            vote={table.pending_vote}
            resolution={voteResolution}
            localPlayerId={localPlayerId}
            onVote={handleVote}
          />
          <PauseBanner table={table} />

          {/* Host approval banner for pending sit requests */}
          {isAdmin && table.pending_sit_requests.length > 0 && (
            <HostApprovalBanner
              requests={table.pending_sit_requests}
              onApprove={(sid) => sendMessage({ type: 'approve_sit_down', session_id: sid })}
              onReject={(sid) => sendMessage({ type: 'reject_sit_down', session_id: sid })}
            />
          )}
        </>
      )}

      {/* Main table area */}
      <main
        className="flex-1 pt-14 relative"
        style={{ paddingBottom: actionBarMode === 'bottom' && localPlayer ? 80 : 0 }}
      >
        {table ? (
          <div className="w-full h-full" style={{ minHeight: 'calc(100vh - 56px)' }}>
            <OvalTable
              table={table}
              localPlayerId={localPlayerId}
              holeCards={holeCards}
              rabbitHuntCards={rabbitHuntCards}
              onSitDown={handleSitDown}
              onRevealCard={handleRevealCard}
              onRabbitHunt={handleRabbitHunt}
              onSeatContextMenu={isAdmin ? handleSeatContextMenu : undefined}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center h-full min-h-[400px]">
            <p className="text-zinc-600 text-sm">Waiting for table state...</p>
          </div>
        )}
      </main>

      {/* Action bars */}
      <AnimatePresence>
        {table && localPlayer && (
          <>
            {actionBarMode === 'bottom' && (
              <BottomActionBar table={table} localPlayer={localPlayer} />
            )}
            {actionBarMode === 'overlay' && (
              <OverlayActionBar table={table} localPlayer={localPlayer} />
            )}
          </>
        )}
      </AnimatePresence>

      {/* Spectator overlay when not seated */}
      {table && !isSeated && (
        <SpectatorOverlay
          spectatorCount={table.spectators.length}
          hasEmptySeat={
            Object.keys(table.players).length < table.rules.max_players
          }
          onTakeSeat={() => {
            // Find first empty seat
            const takenSeats = new Set(Object.values(table.players).map((p) => p.seat))
            for (let s = 0; s < table.rules.max_players; s++) {
              if (!takenSeats.has(s)) {
                handleSitDown(s)
                break
              }
            }
          }}
        />
      )}

      {/* Options drawer */}
      <OptionsDrawer
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        table={table}
        localPlayerId={localPlayerId}
        isSeated={isSeated}
        isAdmin={isAdmin}
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

function SpectatorOverlay({
  spectatorCount,
  hasEmptySeat,
  onTakeSeat,
}: {
  spectatorCount: number
  hasEmptySeat: boolean
  onTakeSeat: () => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="fixed bottom-4 left-0 right-0 flex justify-center px-4 z-30 pointer-events-none"
    >
      <div className="bg-zinc-900/90 backdrop-blur border border-zinc-700 rounded-xl px-4 py-3 flex items-center gap-4 pointer-events-auto shadow-lg max-w-sm w-full">
        <div className="flex-1">
          <p className="text-zinc-400 text-xs">Spectating</p>
          <p className="text-white text-sm font-medium">{spectatorCount} watching</p>
        </div>
        {hasEmptySeat && (
          <button
            onClick={onTakeSeat}
            className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-white text-sm font-semibold transition-colors"
          >
            Take a Seat
          </button>
        )}
      </div>
    </motion.div>
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
