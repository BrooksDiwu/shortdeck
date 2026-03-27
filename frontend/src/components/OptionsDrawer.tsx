import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import type { Table, TableRulesSchema } from '@/types'
import { useGameStore } from '@/stores/gameStore'
import { useSoundStore } from '@/stores/soundStore'
import Modal from './Modal'
import RulesForm from './RulesForm'

interface OptionsDrawerProps {
  open: boolean
  onClose: () => void
  table: Table | null
  localPlayerId?: string | null
  isSeated: boolean
  isAdmin: boolean
  pendingSitOut: boolean
  onRequestSitOut: () => void
  onCancelSitOut: () => void
}

export default function OptionsDrawer({ open, onClose, table, localPlayerId, isSeated, isAdmin, pendingSitOut, onRequestSitOut, onCancelSitOut }: OptionsDrawerProps) {
  const navigate = useNavigate()
  const { sendMessage, setActionBarMode, actionBarMode, disconnect } = useGameStore()
  const { muted, toggleMute } = useSoundStore()
  const [showRuleChange, setShowRuleChange] = useState(false)
  const [showManagePlayers, setShowManagePlayers] = useState(false)
  const [standUpConfirm, setStandUpConfirm] = useState(false)

  const localPlayer = table && localPlayerId
    ? Object.values(table.players).find((p) => p.session_id === localPlayerId) ?? null
    : null
  const isSittingOut = localPlayer?.status === 'sitting_out'
  const isHandActive = table ? !['waiting', 'between_hands'].includes(table.phase) : false

  const handleLeave = () => {
    // If seated and sitting out, stand up first so the seat is freed immediately
    if (isSeated && isSittingOut) {
      sendMessage({ type: 'stand_up' })
    }
    disconnect()
    navigate('/')
  }

  const handleStandUp = () => {
    sendMessage({ type: 'stand_up' })
    setStandUpConfirm(false)
    onClose()
  }

  const handleSitOutClick = () => {
    if (isHandActive) {
      // Queue sit-out for after hand ends
      onRequestSitOut()
      onClose()
    } else {
      sendMessage({ type: 'sit_out' })
      onClose()
    }
  }

  const handleSitIn = () => {
    sendMessage({ type: 'sit_in' })
    onCancelSitOut()
    onClose()
  }

  const handlePause = () => {
    sendMessage({ type: 'pause_request' })
    onClose()
  }

  const handleUnpause = () => {
    sendMessage({ type: 'unpause_request' })
    onClose()
  }

  const handleProposeRuleChange = (rules: TableRulesSchema, force: boolean) => {
    sendMessage(
      force
        ? { type: 'force_rule_change', proposed_rules: rules }
        : { type: 'propose_rule_change', proposed_rules: rules }
    )
    setShowRuleChange(false)
    onClose()
  }

  const MenuItem = ({
    label,
    icon,
    onClick,
    danger = false,
    sublabel,
  }: {
    label: string
    icon: React.ReactNode
    onClick: () => void
    danger?: boolean
    sublabel?: string
  }) => (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 hover:bg-zinc-800 transition-colors text-left rounded-lg ${
        danger ? 'text-red-400 hover:text-red-300' : 'text-zinc-200 hover:text-white'
      }`}
    >
      <span className="w-5 h-5 flex items-center justify-center shrink-0 opacity-70">{icon}</span>
      <div>
        <div className="text-sm font-medium">{label}</div>
        {sublabel && <div className="text-xs text-zinc-500">{sublabel}</div>}
      </div>
    </button>
  )

  return (
    <>
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onClose}
            />
            <motion.div
              className="fixed left-0 top-0 bottom-0 z-50 w-72 bg-zinc-950 border-r border-zinc-800 flex flex-col overflow-y-auto"
              initial={{ x: -288 }}
              animate={{ x: 0 }}
              exit={{ x: -288 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            >
              <div className="flex items-center justify-between p-4 border-b border-zinc-800">
                <h2 className="text-white font-semibold">Options</h2>
                <button onClick={onClose} className="text-zinc-400 hover:text-white transition-colors">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="flex-1 py-2 px-2 flex flex-col gap-1">
                {/* Action bar position */}
                <MenuItem
                  label="Action Bar Position"
                  sublabel={actionBarMode === 'bottom' ? 'Bottom bar' : 'Overlay near seat'}
                  icon={
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h8m-8 6h16" />
                    </svg>
                  }
                  onClick={() => {
                    setActionBarMode(actionBarMode === 'bottom' ? 'overlay' : 'bottom')
                  }}
                />

                {/* Mute */}
                <MenuItem
                  label={muted ? 'Unmute Sounds' : 'Mute Sounds'}
                  icon={
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-4 h-4">
                      {muted ? (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M9 9l-4.5 4.5M6 18V6l6 6" />
                      ) : (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072M12 6v12m0 0l-4.243-4.243M12 18l4.243-4.243" />
                      )}
                    </svg>
                  }
                  onClick={toggleMute}
                />

                <div className="border-t border-zinc-800 my-1" />

                {/* Propose rule change */}
                <MenuItem
                  label="Propose Rule Change"
                  icon={
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  }
                  onClick={() => setShowRuleChange(true)}
                />

                {/* Pause */}
                {!table?.is_paused ? (
                  <MenuItem
                    label="Pause Before Next Hand"
                    icon={
                      <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    }
                    onClick={handlePause}
                  />
                ) : (
                  <MenuItem
                    label="Unpause Game"
                    icon={
                      <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    }
                    onClick={handleUnpause}
                  />
                )}

                {/* Sit out / sit in / stand up */}
                {isSeated && !isSittingOut && (
                  <MenuItem
                    label={pendingSitOut ? 'Sitting Out After Hand' : 'Sit Out Next Hand'}
                    sublabel={pendingSitOut ? 'Tap to cancel' : 'Skip next hand(s)'}
                    icon={
                      <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    }
                    onClick={pendingSitOut ? () => { onCancelSitOut(); onClose() } : handleSitOutClick}
                  />
                )}
                {isSeated && isSittingOut && (
                  <>
                    <MenuItem
                      label="Sit Back In"
                      sublabel="You will be dealt in next hand"
                      icon={
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-4 h-4">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                      }
                      onClick={handleSitIn}
                    />
                    <MenuItem
                      label="Stand Up"
                      sublabel="Cash out and return to spectator"
                      icon={
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-4 h-4">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                      }
                      onClick={() => setStandUpConfirm(true)}
                    />
                  </>
                )}

                <div className="border-t border-zinc-800 my-1" />

                {/* Host: manage players */}
                {isAdmin && (
                  <MenuItem
                    label="Manage Players"
                    icon={
                      <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                    }
                    onClick={() => setShowManagePlayers(true)}
                  />
                )}

                {/* Return to lobby */}
                <MenuItem
                  label="Return to Lobby"
                  danger
                  icon={
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                  }
                  onClick={handleLeave}
                />
              </div>

              {/* Table info footer */}
              {table && (
                <div className="p-4 border-t border-zinc-800 text-zinc-600 text-xs">
                  <div>Table: {table.table_id}</div>
                  <div>Seq: {table.action_seq}</div>
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Rule change modal */}
      <Modal
        open={showRuleChange}
        onClose={() => setShowRuleChange(false)}
        title="Propose Rule Change"
        className="max-w-lg"
      >
        {table && (
          <RulesForm
            defaultRules={table.rules}
            onSubmit={(rules) => handleProposeRuleChange(rules, false)}
            onForceSubmit={isAdmin ? (rules) => handleProposeRuleChange(rules, true) : undefined}
            onCancel={() => setShowRuleChange(false)}
            submitLabel="Propose Change"
          />
        )}
      </Modal>

      {/* Stand up confirm */}
      <Modal
        open={standUpConfirm}
        onClose={() => setStandUpConfirm(false)}
        title="Stand Up?"
      >
        <p className="text-zinc-300 text-sm mb-4">Stand up and return to spectator view?</p>
        <div className="flex gap-3">
          <button
            className="flex-1 py-2 rounded-lg bg-zinc-700 hover:bg-zinc-600 text-white text-sm"
            onClick={() => setStandUpConfirm(false)}
          >
            Cancel
          </button>
          <button
            className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white font-semibold text-sm"
            onClick={handleStandUp}
          >
            Stand Up
          </button>
        </div>
      </Modal>

      {/* Manage players modal */}
      <Modal
        open={showManagePlayers}
        onClose={() => setShowManagePlayers(false)}
        title="Manage Players"
        className="max-w-lg"
      >
        {table && (
          <ManagePlayersPanel table={table} onClose={() => setShowManagePlayers(false)} />
        )}
      </Modal>
    </>
  )
}

function ManagePlayersPanel({ table, onClose }: { table: Table; onClose: () => void }) {
  const sendMessage = useGameStore((s) => s.sendMessage)

  return (
    <div className="flex flex-col gap-4">
      {/* Seated players */}
      <div>
        <h3 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-2">Seated Players</h3>
        <div className="flex flex-col gap-2">
          {Object.values(table.players).map((player) => (
            <div key={player.session_id} className="flex items-center justify-between bg-zinc-800 rounded-lg px-3 py-2">
              <div>
                <div className="text-white text-sm font-medium">{player.name}</div>
                <div className="text-zinc-400 text-xs">Seat {player.seat} • {player.status}</div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => sendMessage({ type: 'host_stand_up', session_id: player.session_id })}
                  className="px-2 py-1 bg-yellow-600/20 hover:bg-yellow-600/40 text-yellow-400 text-xs rounded transition-colors border border-yellow-600/30"
                >
                  Stand Up
                </button>
                <button
                  onClick={() => {
                    if (confirm(`Remove ${player.name} from table?`)) {
                      sendMessage({ type: 'host_remove_player', session_id: player.session_id })
                    }
                  }}
                  className="px-2 py-1 bg-red-600/20 hover:bg-red-600/40 text-red-400 text-xs rounded transition-colors border border-red-600/30"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
          {Object.keys(table.players).length === 0 && (
            <p className="text-zinc-500 text-sm">No players seated</p>
          )}
        </div>
      </div>

      {/* Pending sit requests */}
      {table.pending_sit_requests.length > 0 && (
        <div>
          <h3 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-2">Pending Sit Requests</h3>
          <div className="flex flex-col gap-2">
            {table.pending_sit_requests.map((req) => (
              <div key={req.session_id} className="flex items-center justify-between bg-zinc-800 rounded-lg px-3 py-2">
                <div>
                  <div className="text-white text-sm font-medium">{req.session_id.slice(0, 8)}</div>
                  <div className="text-zinc-400 text-xs">Seat {req.seat} • {req.chips} chips</div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => sendMessage({ type: 'approve_sit_down', session_id: req.session_id })}
                    className="px-2 py-1 bg-green-600/20 hover:bg-green-600/40 text-green-400 text-xs rounded transition-colors border border-green-600/30"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => sendMessage({ type: 'reject_sit_down', session_id: req.session_id })}
                    className="px-2 py-1 bg-red-600/20 hover:bg-red-600/40 text-red-400 text-xs rounded transition-colors border border-red-600/30"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Spectators */}
      {table.spectators.length > 0 && (
        <div>
          <h3 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-2">Spectators</h3>
          <p className="text-zinc-400 text-sm">{table.spectators.length} watching</p>
        </div>
      )}

      <button
        onClick={onClose}
        className="mt-2 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-white text-sm transition-colors"
      >
        Done
      </button>
    </div>
  )
}
