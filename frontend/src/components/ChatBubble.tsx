import { useState, useRef, useEffect } from 'react'

interface Message {
  user: string
  text: string
}

const INITIAL_MESSAGES: Message[] = [
  { user: 'Phil', text: 'Nice hand!' },
  { user: 'Sara', text: 'gg' },
  { user: 'Mike', text: 'All in next round 😤' },
]

export default function ChatBubble() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES)
  const [input, setInput] = useState('')
  const panelRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, open])

  const send = () => {
    if (!input.trim()) return
    setMessages((m) => [...m, { user: 'You', text: input.trim() }])
    setInput('')
  }

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="absolute bottom-3 right-3 z-50 w-10 h-10 rounded-full bg-zinc-800 border border-zinc-600 flex items-center justify-center shadow-lg active:scale-95 transition-transform"
          aria-label="Open chat"
        >
          <svg
            className="w-5 h-5 text-yellow-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        </button>
      )}

      {open && (
        <div
          ref={panelRef}
          className="absolute bottom-14 right-3 z-50 w-56 h-64 bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="px-3 py-2 border-b border-zinc-700 flex items-center justify-between">
            <span className="text-xs font-bold text-yellow-400">Table Chat</span>
            <button
              onClick={() => setOpen(false)}
              className="text-zinc-500 hover:text-zinc-300 transition-colors"
              aria-label="Close chat"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5">
            {messages.map((m, i) => (
              <div key={i} className="text-[11px]">
                <span className="font-bold text-yellow-300">{m.user}: </span>
                <span className="text-zinc-300">{m.text}</span>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input row */}
          <div className="flex items-center border-t border-zinc-700 p-1.5 gap-1">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
              placeholder="Type..."
              className="flex-1 bg-zinc-800 text-zinc-200 text-[11px] rounded px-2 py-1 outline-none placeholder:text-zinc-500"
            />
            <button
              onClick={send}
              className="text-yellow-400 active:scale-90 transition-transform"
              aria-label="Send message"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  )
}
