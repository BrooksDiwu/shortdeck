import { useSoundStore } from '@/stores/soundStore'
import type { Table } from '@/types'
import { getGameModeLabel, formatBlinds, truncateId } from '@/utils/gameUtils'

interface TopBarProps {
  table: Table | null
  onMenuOpen: () => void
}

export default function TopBar({ table, onMenuOpen }: TopBarProps) {
  const { muted, toggleMute } = useSoundStore()

  return (
    <div className="fixed top-0 left-0 right-0 z-30 h-14 flex items-center justify-between px-4 bg-zinc-950/95 backdrop-blur border-b border-zinc-800">
      {/* Left: menu */}
      <button
        onClick={onMenuOpen}
        className="p-2 rounded-lg hover:bg-zinc-800 transition-colors text-zinc-300 hover:text-white"
        aria-label="Open options menu"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {/* Center: table name */}
      <div className="flex flex-col items-center">
        <span className="text-white text-sm font-semibold leading-none">
          {table ? truncateId(table.table_id) : 'Loading...'}
        </span>
        {table && (
          <span className="text-zinc-500 text-[10px] mt-0.5">
            {table.phase === 'waiting' ? 'Waiting' : `Hand #${table.hand_number}`}
          </span>
        )}
      </div>

      {/* Right: game info + mute */}
      <div className="flex items-center gap-3">
        {table && (
          <div className="text-right">
            <div className="text-green-400 text-xs font-semibold leading-none">
              {getGameModeLabel(table.rules)}
            </div>
            <div className="text-zinc-400 text-[10px] mt-0.5">
              {formatBlinds(table.rules)}
            </div>
          </div>
        )}

        {table && (
          <div className="text-zinc-400 text-[10px]">
            {Object.keys(table.players).length}/{table.rules.max_players}
          </div>
        )}

        <button
          onClick={toggleMute}
          className="p-2 rounded-lg hover:bg-zinc-800 transition-colors text-zinc-400 hover:text-white"
          aria-label={muted ? 'Unmute' : 'Mute'}
        >
          {muted ? (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072M12 6v12m0 0l-4.243-4.243M12 18l4.243-4.243M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
            </svg>
          )}
        </button>
      </div>
    </div>
  )
}
