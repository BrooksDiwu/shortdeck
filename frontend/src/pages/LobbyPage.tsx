import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import type { TableResponse, TableRulesSchema } from '@/types'
import { useSessionStore } from '@/stores/sessionStore'
import { api } from '@/utils/api'
import { getGameModeLabel, formatBlinds, truncateId } from '@/utils/gameUtils'
import Modal from '@/components/Modal'
import RulesForm from '@/components/RulesForm'

export default function LobbyPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { createSession } = useSessionStore()

  const [tables, setTables] = useState<TableResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [banner, setBanner] = useState<string | null>((location.state as { error?: string } | null)?.error ?? null)

  // Modal states
  const [nameModalOpen, setNameModalOpen] = useState(false)
  const [nameInput, setNameInput] = useState('')
  const [nameError, setNameError] = useState('')
  const [nameLoading, setNameLoading] = useState(false)

  // Pending action after name entry
  const [pendingAction, setPendingAction] = useState<
    { type: 'join'; tableId: string } | { type: 'create' } | null
  >(null)

  // Create table form
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [tableName, setTableName] = useState('')
  const [createLoading, setCreateLoading] = useState(false)
  const [createError, setCreateError] = useState('')

  const fetchTables = useCallback(async () => {
    try {
      const data = await api.getTables()
      setTables(data.sort((a, b) => b.player_count - a.player_count))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTables()
    const interval = setInterval(fetchTables, 5000)
    return () => clearInterval(interval)
  }, [fetchTables])

  const requireName = (action: typeof pendingAction) => {
    setPendingAction(action)
    setNameModalOpen(true)
    setNameInput('')
    setNameError('')
  }

  const handleNameSubmit = async () => {
    if (!nameInput.trim()) {
      setNameError('Please enter a display name')
      return
    }
    setNameLoading(true)
    setNameError('')
    try {
      const name = nameInput.trim()
      if (pendingAction?.type === 'join') {
        await doJoin(pendingAction.tableId, name)
      } else if (pendingAction?.type === 'create') {
        // For create, we need a session first — create it then open the modal
        await createSession(name)
        setNameModalOpen(false)
        setCreateModalOpen(true)
      }
    } catch (e) {
      setNameError((e as Error).message)
    } finally {
      setNameLoading(false)
    }
  }

  const doJoin = async (tableId: string, name: string) => {
    // Create session right before joining; if join fails, clear it
    await createSession(name)
    const currentToken = useSessionStore.getState().token
    if (!currentToken) return
    try {
      await api.joinTable(currentToken, tableId)
      setNameModalOpen(false)
      navigate(`/table/${tableId}`)
    } catch (e) {
      useSessionStore.getState().clearSession()
      throw e
    }
  }

  const handleCreateTable = async (rules: TableRulesSchema) => {
    const currentToken = useSessionStore.getState().token
    if (!currentToken) return
    setCreateLoading(true)
    setCreateError('')
    try {
      const table = await api.createTable(currentToken, rules, tableName)
      await api.joinTable(currentToken, table.table_id)
      navigate(`/table/${table.table_id}`)
    } catch (e) {
      useSessionStore.getState().clearSession()
      setCreateError((e as Error).message)
    } finally {
      setCreateLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col">
      {/* Header */}
      <header className="pt-12 pb-6 px-4 text-center">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="inline-flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-full bg-green-600 flex items-center justify-center">
              <span className="text-white text-lg">♠</span>
            </div>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Shortdeck Hold'em</h1>
          <p className="text-zinc-500 text-sm mt-1">Real-time multiplayer poker</p>
        </motion.div>
      </header>

      {/* Error banner */}
      {banner && (
        <div className="max-w-2xl mx-auto w-full px-4 mb-2">
          <div className="flex items-center justify-between gap-3 bg-red-900/40 border border-red-700/50 rounded-lg px-4 py-3">
            <p className="text-red-400 text-sm">{banner}</p>
            <button onClick={() => setBanner(null)} className="text-red-400 hover:text-red-200 text-lg leading-none shrink-0">&times;</button>
          </div>
        </div>
      )}

      {/* Table list */}
      <main className="flex-1 px-4 pb-32 max-w-2xl mx-auto w-full">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="w-6 h-6 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={fetchTables}
              className="mt-3 text-zinc-400 hover:text-white text-sm underline"
            >
              Retry
            </button>
          </div>
        ) : tables.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-16"
          >
            <div className="text-6xl mb-4">♣</div>
            <p className="text-zinc-400 text-lg font-medium">No tables open</p>
            <p className="text-zinc-600 text-sm mt-1">Create one to get started</p>
          </motion.div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <AnimatePresence>
              {tables.map((table, i) => (
                <motion.div
                  key={table.table_id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="bg-zinc-900 border border-zinc-800 hover:border-zinc-600 rounded-xl p-4 flex flex-col gap-3 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-white font-semibold text-sm truncate">
                        {table.name || truncateId(table.table_id)}
                      </h3>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className="text-green-400 text-xs font-semibold bg-green-400/10 px-2 py-0.5 rounded-full">
                          {getGameModeLabel(table.rules)}
                        </span>
                        <span className="text-zinc-400 text-xs">
                          {formatBlinds(table.rules)}
                        </span>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-white text-sm font-mono">
                        {table.player_count}
                        <span className="text-zinc-600">/{table.rules.max_players}</span>
                      </div>
                      <div className="text-zinc-600 text-[10px]">players</div>
                    </div>
                  </div>

                  {/* Phase indicator */}
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        table.phase === 'waiting' ? 'bg-zinc-500' : 'bg-green-500 animate-pulse'
                      }`}
                    />
                    <span className="text-zinc-500 text-xs capitalize">{table.phase}</span>
                  </div>

                  <button
                    onClick={() => requireName({ type: 'join', tableId: table.table_id })}
                    disabled={table.player_count >= table.rules.max_players && table.phase !== 'waiting'}
                    className="w-full py-2.5 bg-green-700 hover:bg-green-600 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed rounded-lg text-white text-sm font-semibold transition-colors"
                  >
                    {table.player_count >= table.rules.max_players ? 'Spectate' : 'Join'}
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </main>

      {/* Sticky create button */}
      <div className="fixed bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-zinc-950 to-transparent pointer-events-none">
        <div className="max-w-2xl mx-auto pointer-events-auto">
          <button
            onClick={() => requireName({ type: 'create' })}
            className="w-full py-4 bg-green-600 hover:bg-green-500 active:bg-green-700 rounded-xl text-white font-bold text-base transition-colors shadow-lg shadow-green-900/40"
          >
            Create Table
          </button>
        </div>
      </div>

      {/* Name entry modal */}
      <Modal
        open={nameModalOpen}
        onClose={() => setNameModalOpen(false)}
        title="Enter Your Name"
      >
        <div className="flex flex-col gap-4">
          <p className="text-zinc-400 text-sm">Choose a display name for this session.</p>
          <input
            type="text"
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-green-500 placeholder:text-zinc-600"
            placeholder="Your name"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void handleNameSubmit()}
            autoFocus
            maxLength={24}
          />
          {nameError && <p className="text-red-400 text-sm">{nameError}</p>}
          <div className="flex gap-3">
            <button
              className="flex-1 py-2.5 bg-zinc-700 hover:bg-zinc-600 rounded-xl text-white text-sm transition-colors"
              onClick={() => setNameModalOpen(false)}
            >
              Cancel
            </button>
            <button
              className="flex-1 py-2.5 bg-green-600 hover:bg-green-500 rounded-xl text-white font-semibold text-sm transition-colors disabled:opacity-50"
              onClick={() => void handleNameSubmit()}
              disabled={nameLoading}
            >
              {nameLoading ? 'Loading...' : 'Continue'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Create table modal */}
      <Modal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Create Table"
        className="max-w-lg"
      >
        <div className="overflow-y-auto max-h-[70vh] pr-1">
          {createError && (
            <div className="mb-4 p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-red-400 text-sm">
              {createError}
            </div>
          )}
          <RulesForm
            showTableName
            tableName={tableName}
            onTableNameChange={setTableName}
            onSubmit={(rules) => void handleCreateTable(rules)}
            onCancel={() => setCreateModalOpen(false)}
            submitLabel={createLoading ? 'Creating...' : 'Create Table'}
          />
        </div>
      </Modal>
    </div>
  )
}
