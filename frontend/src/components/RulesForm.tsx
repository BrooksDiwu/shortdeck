import { useState } from 'react'
import type { TableRulesSchema } from '@/types'

const DEFAULT_RULES: TableRulesSchema = {
  variant: 'holdem',
  betting: 'no_limit',
  small_blind: 10,
  big_blind: 20,
  denomination: 'chips',
  hole_cards_count: 2,
  extra_hole_card: false,
  must_use_exactly_two_hole_cards: false,
  extra_board: false,
  extra_flop: false,
  street_modifiers: {},
  max_players: 9,
  allow_rebuy: true,
  timer_enabled: false,
  timer_seconds: 30,
}

function InputRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-zinc-400 text-xs font-medium">{label}</label>
      {children}
    </div>
  )
}

interface RulesFormProps {
  defaultRules?: Partial<TableRulesSchema>
  onSubmit: (rules: TableRulesSchema) => void
  onForceSubmit?: (rules: TableRulesSchema) => void
  onCancel?: () => void
  submitLabel?: string
  showTableName?: boolean
  onTableNameChange?: (name: string) => void
  tableName?: string
}

export default function RulesForm({
  defaultRules,
  onSubmit,
  onForceSubmit,
  onCancel,
  submitLabel = 'Create Table',
  showTableName = false,
  onTableNameChange,
  tableName = '',
}: RulesFormProps) {
  const [rules, setRules] = useState<TableRulesSchema>({ ...DEFAULT_RULES, ...defaultRules })
  const [showAdvanced, setShowAdvanced] = useState(false)

  const computeCap = (r: TableRulesSchema): number => {
    const deck = r.variant === 'shortdeck' ? 36 : 52
    const base: Record<string, number> = { flop: 3, turn: 1, river: 1 }
    const boards = (r.extra_board || r.extra_flop) ? 2 : 1
    const boardCards = Object.entries(base).reduce((sum, [s, b]) => sum + Math.max(0, b + (r.street_modifiers[s] ?? 0)), 0)
    const hole = r.hole_cards_count + (r.extra_hole_card ? 1 : 0)
    return Math.min(9, Math.floor((deck - boards * boardCards) / hole))
  }

  const set = <K extends keyof TableRulesSchema>(key: K, value: TableRulesSchema[K]) => {
    setRules((r) => {
      const next = { ...r, [key]: value } as TableRulesSchema
      if (key === 'extra_board' || key === 'extra_flop') {
        const enabled = Boolean(value)
        next.extra_board = enabled
        next.extra_flop = enabled
      }
      const cap = computeCap(next)
      return { ...next, max_players: Math.min(next.max_players, cap) }
    })
  }

  // Sync variant+betting to a friendly "game mode" selector
  const gameModeValue = `${rules.variant}:${rules.betting}`
  const setGameMode = (v: string) => {
    const [variant, betting] = v.split(':') as [TableRulesSchema['variant'], TableRulesSchema['betting']]
    const isPLO = betting === 'pot_limit'
    const holeCount = isPLO ? 4 : 2
    setRules((r) => {
      const next = { ...r, variant, betting, hole_cards_count: holeCount, must_use_exactly_two_hole_cards: isPLO }
      const cap = computeCap(next)
      return { ...next, max_players: Math.min(next.max_players, cap) }
    })
  }

  const maxPlayersCap = computeCap(rules)

  const inputClass =
    'bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-green-500 w-full'
  const selectClass =
    'bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-green-500 w-full'

  return (
    <div className="flex flex-col gap-4">
      {/* Table name */}
      {showTableName && (
        <InputRow label="Table Name (display only)">
          <input
            type="text"
            className={inputClass}
            value={tableName}
            onChange={(e) => onTableNameChange?.(e.target.value)}
            placeholder="My Table"
            maxLength={32}
          />
        </InputRow>
      )}

      {/* Game mode */}
      <InputRow label="Game Mode">
        <select className={selectClass} value={gameModeValue} onChange={(e) => setGameMode(e.target.value)}>
          <option value="holdem:no_limit">No Limit Hold'em (NLH)</option>
          <option value="shortdeck:no_limit">No Limit Shortdeck</option>
          <option value="holdem:pot_limit">Pot Limit Omaha (PLO)</option>
          <option value="shortdeck:pot_limit">PLO Shortdeck</option>
        </select>
      </InputRow>

      {/* Blinds */}
      <div className="grid grid-cols-2 gap-3">
        <InputRow label="Small Blind">
          <input
            type="number"
            className={inputClass}
            value={rules.small_blind}
            min={1}
            onChange={(e) => set('small_blind', Number(e.target.value))}
          />
        </InputRow>
        <InputRow label="Big Blind">
          <input
            type="number"
            className={inputClass}
            value={rules.big_blind}
            min={2}
            onChange={(e) => set('big_blind', Number(e.target.value))}
          />
        </InputRow>
      </div>

      {/* Max players */}
      <InputRow label={`Max Players: ${rules.max_players}`}>
        <input
          type="range"
          min={2}
          max={maxPlayersCap}
          value={rules.max_players}
          onChange={(e) => set('max_players', Number(e.target.value))}
          className="w-full accent-green-500"
        />
        <div className="flex justify-between text-zinc-600 text-xs mt-1">
          {[2, 3, 4, 5, 6, 7, 8, 9].filter((n) => n <= maxPlayersCap).map((n) => (
            <span key={n} className={rules.max_players === n ? 'text-green-400' : ''}>
              {n}
            </span>
          ))}
        </div>
      </InputRow>

      {/* Advanced toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="flex items-center gap-2 text-zinc-400 hover:text-white text-sm transition-colors"
      >
        <svg
          className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        Advanced Options
      </button>

      {showAdvanced && (
        <div className="flex flex-col gap-4 border-t border-zinc-800 pt-4">
          {/* Denomination */}
          <InputRow label="Denomination">
            <select
              className={selectClass}
              value={rules.denomination}
              onChange={(e) => set('denomination', e.target.value as 'chips' | 'usd')}
            >
              <option value="chips">Chips</option>
              <option value="usd">USD</option>
            </select>
          </InputRow>

          {/* Hole cards count */}
          <InputRow label="Hole Cards Count">
            <input
              type="number"
              className={inputClass}
              min={2}
              max={4}
              value={rules.hole_cards_count}
              onChange={(e) => set('hole_cards_count', Number(e.target.value))}
            />
          </InputRow>

          {/* Street card counts */}
          <div className="flex flex-col gap-2">
            <label className="text-zinc-400 text-xs font-medium">Community Cards Per Street</label>
            <div className="grid grid-cols-3 gap-2">
              {([
                { street: 'flop', base: 3, label: 'Flop', min: 1, max: 5 },
                { street: 'turn', base: 1, label: 'Turn', min: 0, max: 3 },
                { street: 'river', base: 1, label: 'River', min: 0, max: 3 },
              ] as const).map(({ street, base, label, min, max }) => {
                const current = base + (rules.street_modifiers[street] ?? 0)
                return (
                  <div key={street} className="flex flex-col gap-1">
                    <label className="text-zinc-500 text-xs text-center">{label}</label>
                    <input
                      type="number"
                      className={inputClass + ' text-center'}
                      min={min}
                      max={max}
                      value={current}
                      onChange={(e) => {
                        const val = Number(e.target.value)
                        const mod = val - base
                        const newMods = { ...rules.street_modifiers }
                        if (mod === 0) {
                          delete newMods[street]
                        } else {
                          newMods[street] = mod
                        }
                        set('street_modifiers', newMods)
                      }}
                    />
                  </div>
                )
              })}
            </div>
          </div>

          {/* Checkboxes */}
          {[
            { key: 'extra_hole_card', label: 'Extra Hole Card' },
            { key: 'must_use_exactly_two_hole_cards', label: 'Must Use Exactly 2 Hole Cards' },
            { key: 'extra_board', label: 'Extra Board' },
            { key: 'allow_rebuy', label: 'Allow Rebuy' },
            { key: 'timer_enabled', label: 'Turn Timer' },
          ].map(({ key, label }) => (
            <label key={key} className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={rules[key as keyof TableRulesSchema] as boolean}
                onChange={(e) => set(key as keyof TableRulesSchema, e.target.checked as never)}
                className="w-4 h-4 rounded accent-green-500"
              />
              <span className="text-zinc-200 text-sm">{label}</span>
            </label>
          ))}

          {/* Timer seconds (conditional) */}
          {rules.timer_enabled && (
            <InputRow label={`Timer Duration: ${rules.timer_seconds}s`}>
              <input
                type="range"
                min={10}
                max={120}
                step={5}
                value={rules.timer_seconds}
                onChange={(e) => set('timer_seconds', Number(e.target.value))}
                className="w-full accent-green-500"
              />
            </InputRow>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-col gap-2 pt-2 border-t border-zinc-800">
        <button
          type="button"
          onClick={() => onSubmit(rules)}
          className="w-full py-3 bg-green-600 hover:bg-green-500 rounded-xl font-semibold text-white transition-colors"
        >
          {submitLabel}
        </button>

        {onForceSubmit && (
          <button
            type="button"
            onClick={() => onForceSubmit(rules)}
            className="w-full py-2.5 bg-amber-600/30 hover:bg-amber-600/50 border border-amber-600/50 rounded-xl font-semibold text-amber-400 text-sm transition-colors"
          >
            Force Change (no vote)
          </button>
        )}

        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="w-full py-2.5 bg-zinc-800 hover:bg-zinc-700 rounded-xl text-zinc-300 text-sm transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  )
}
