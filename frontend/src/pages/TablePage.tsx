import { useEffect, useRef, useState } from 'react'
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
import { api } from '@/utils/api'
import HostApprovalBanner from '@/components/HostApprovalBanner'
import ConnectionStatus from '@/components/ConnectionStatus'
import HandLogModal from '@/components/poker/HandLogModal'
import LeaderboardModal from '@/components/poker/LeaderboardModal'

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
    serverError,
    clearServerError,
  } = useGameStore()

  // GSAP chip animations
  useChipAnimations()

  const [menuOpen, setMenuOpen] = useState(false)
  const [sitSeat, setSitSeat] = useState<number | null>(null)
  const [sitDownOpen, setSitDownOpen] = useState(false)
  const [isBustRebuy, setIsBustRebuy] = useState(false)
  const [contextMenuSeat, setContextMenuSeat] = useState<{ seat: number; x: number; y: number } | null>(null)
  const [pendingSitOut, setPendingSitOut] = useState(false)
  const [handLogOpen, setHandLogOpen] = useState(false)
  const [leaderboardOpen, setLeaderboardOpen] = useState(false)

  // Auto-dismiss server error toast
  useEffect(() => {
    if (!serverError) return
    const t = setTimeout(clearServerError, 4000)
    return () => clearTimeout(t)
  }, [serverError, clearServerError])

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
  const localPlayer = table && localPlayerId
    ? Object.values(table.players).find((p) => p.session_id === localPlayerId) ?? null
    : null
  const localPlayerStatus = localPlayer?.status
  useEffect(() => {
    if (localPlayerStatus === 'sitting_out') setPendingSitOut(false)
  }, [localPlayerStatus])

  // Auto-open rebuy modal when local player busts
  const localPlayerStack = localPlayer?.stack ?? null
  const localPlayerSeat = localPlayer?.seat ?? null
  useEffect(() => {
    if (
      localPlayerStatus === 'sitting_out' &&
      localPlayerStack !== null &&
      localPlayerStack <= 0 &&
      localPlayerSeat !== null
    ) {
      setSitSeat(localPlayerSeat)
      setIsBustRebuy(true)
      setSitDownOpen(true)
    }
  }, [localPlayerStatus, localPlayerStack, localPlayerSeat])

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

  const isAdmin = table?.admin_id === localPlayerId
  const isSeated = localPlayer !== null

  // Auto-open sit modal for admin if not yet seated
  const adminSitOpenedRef = useRef(false)
  useEffect(() => {
    if (!table || !localPlayerId) return
    if (table.admin_id !== localPlayerId) return
    const alreadySeated = Object.values(table.players).some(p => p.session_id === localPlayerId)
    if (alreadySeated) {
      adminSitOpenedRef.current = true // mark as done so we don't re-open on reconnect
      return
    }
    if (adminSitOpenedRef.current) return
    if (sitDownOpen) return
    adminSitOpenedRef.current = true
    const takenSeats = new Set(Object.values(table.players).map(p => p.seat))
    const firstFree = Array.from({ length: table.rules.max_players }, (_, i) => i).find(s => !takenSeats.has(s)) ?? 0
    setSitSeat(firstFree)
    setSitDownOpen(true)
  }, [table?.admin_id, localPlayerId, Object.keys(table?.players ?? {}).length])

  // Debug logging
  console.log('[TablePage] isAdmin:', isAdmin, 'localPlayerId:', localPlayerId, 'pending_sit_requests:', table?.pending_sit_requests)

  const handleSitDown = (seat: number) => {
    setSitSeat(seat)
    setSitDownOpen(true)
  }

  const handleSitDownConfirm = async (seat: number, chips: number) => {
    if (isBustRebuy) {
      if (!token || !tableId) return
      try {
        await api.rebuy(token, tableId, chips)
      } catch (_e) {
        // error shown via server error toast
      }
    } else {
      sendMessage({ type: 'sit_down_request', seat, chips })
    }
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

      {/* Server error toast */}
      <AnimatePresence>
        {serverError && (
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 40 }}
            className="fixed bottom-24 left-0 right-0 z-50 flex justify-center px-4 pointer-events-none"
          >
            <div className="bg-red-900/95 border border-red-700 rounded-xl px-4 py-3 flex items-center gap-3 max-w-sm w-full shadow-2xl pointer-events-auto">
              <span className="text-red-200 text-sm flex-1">{serverError}</span>
              <button onClick={clearServerError} className="text-red-400 hover:text-red-200 shrink-0">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Mobile poker table — fills full screen */}
      {table ? (
        <PokerTable
          table={table}
          localPlayerId={localPlayerId}
          holeCards={holeCards}
          onMenuOpen={() => setMenuOpen(true)}
          onHandLogOpen={() => setHandLogOpen(true)}
          onLeaderboardOpen={() => setLeaderboardOpen(true)}
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
        onConfirm={(seat, chips) => void handleSitDownConfirm(seat, chips)}
        onClose={() => { setSitDownOpen(false); setIsBustRebuy(false) }}
        isRebuy={isBustRebuy}
        isAdmin={isAdmin && !isBustRebuy}
      />

      {table && (
        <HandLogModal
          open={handLogOpen}
          onClose={() => setHandLogOpen(false)}
          entries={table.hand_log}
          denomination={table.rules.denomination}
        />
      )}

      {table && (
        <LeaderboardModal
          open={leaderboardOpen}
          onClose={() => setLeaderboardOpen(false)}
          table={table}
        />
      )}

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
