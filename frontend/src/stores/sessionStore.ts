import { create } from 'zustand'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const SESSION_KEY = 'poker_session'

interface PersistedSession {
  sessionId: string
  token: string
  name: string
  expiresAt: string
}

function loadSession(): Partial<SessionState> {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return {}
    const s = JSON.parse(raw) as PersistedSession
    const expiresAt = new Date(s.expiresAt)
    if (expiresAt <= new Date()) {
      sessionStorage.removeItem(SESSION_KEY)
      return {}
    }
    return { sessionId: s.sessionId, token: s.token, name: s.name, expiresAt }
  } catch {
    return {}
  }
}

function saveSession(sessionId: string, token: string, name: string, expiresAt: Date) {
  const s: PersistedSession = { sessionId, token, name, expiresAt: expiresAt.toISOString() }
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(s))
}

function clearPersistedSession() {
  sessionStorage.removeItem(SESSION_KEY)
}

interface SessionState {
  sessionId: string | null
  token: string | null
  name: string | null
  expiresAt: Date | null

  createSession: (name: string) => Promise<void>
  clearSession: () => void
  isExpiringSoon: () => boolean
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessionId: null,
  token: null,
  name: null,
  expiresAt: null,
  ...loadSession(),

  createSession: async (name: string) => {
    const res = await fetch(`${API_URL}/api/v1/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (!res.ok) {
      const err = await res.text()
      throw new Error(`Failed to create session: ${err}`)
    }
    const data = await res.json() as { session_id: string; token: string; expires_at: string }
    const expiresAt = new Date(data.expires_at)
    saveSession(data.session_id, data.token, name, expiresAt)
    set({ sessionId: data.session_id, token: data.token, name, expiresAt })
  },

  clearSession: () => {
    clearPersistedSession()
    set({ sessionId: null, token: null, name: null, expiresAt: null })
  },

  isExpiringSoon: () => {
    const { expiresAt } = get()
    if (!expiresAt) return false
    const fiveMinutes = 5 * 60 * 1000
    return expiresAt.getTime() - Date.now() < fiveMinutes
  },
}))
