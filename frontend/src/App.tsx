import { Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { useSoundStore } from '@/stores/soundStore'
import { useSessionStore } from '@/stores/sessionStore'
import LobbyPage from '@/pages/LobbyPage'
import TablePage from '@/pages/TablePage'

export default function App() {
  const loadSounds = useSoundStore((s) => s.load)
  const { isExpiringSoon, createSession, name } = useSessionStore()

  useEffect(() => {
    loadSounds()
  }, [loadSounds])

  // Refresh session on tab focus if near expiry
  useEffect(() => {
    const handleFocus = () => {
      if (isExpiringSoon() && name) {
        createSession(name).catch(console.error)
      }
    }
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [isExpiringSoon, createSession, name])

  return (
    <Routes>
      <Route path="/" element={<LobbyPage />} />
      <Route path="/table/:id" element={<TablePage />} />
    </Routes>
  )
}
