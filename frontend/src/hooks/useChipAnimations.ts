import { useEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { useGameStore } from '@/stores/gameStore'
import { getChipTokenCount, CHIP_DENOMINATIONS } from '@/utils/gameUtils'

/**
 * Attaches GSAP chip animations to DOM elements.
 * Call this hook in a component that has access to the table container.
 *
 * - Bets collect into pot at end of each street (phase change)
 * - Pot pays out to winner at hand complete (between_hands phase)
 */
export function useChipAnimations() {
  const table = useGameStore((s) => s.table)
  const prevPhaseRef = useRef<string | undefined>(undefined)
  const prevPotRef = useRef<number>(0)

  useEffect(() => {
    if (!table) return

    const currentPhase = table.phase

    // Detect street change → animate bets into pot
    if (
      prevPhaseRef.current &&
      prevPhaseRef.current !== currentPhase &&
      ['flop', 'turn', 'river', 'showdown', 'between_hands'].includes(currentPhase)
    ) {
      animateBetsToPot(table)
    }

    // Detect hand complete → animate pot to winner
    if (currentPhase === 'between_hands' && prevPhaseRef.current !== 'between_hands') {
      const totalChips = Object.values(table.players).reduce((sum, p) => sum + p.stack, 0) + table.pot
      const tokenCount = getChipTokenCount(prevPotRef.current, totalChips)
      const activePlayers = Object.values(table.players).filter(
        (p) => p.status === 'active' || p.status === 'all_in'
      )
      if (activePlayers.length === 1) {
        animatePotToSeat(activePlayers[0].seat, tokenCount, prevPotRef.current)
      }
    }

    prevPhaseRef.current = currentPhase
    prevPotRef.current = table.pot
  }, [table?.phase, table?.pot])
}

function animateBetsToPot(_table: import('@/types').Table) {
  const potEl = document.getElementById('pot-display')
  if (!potEl) return
  const potRect = potEl.getBoundingClientRect()

  // Find all seat elements with active bets
  const seatEls = document.querySelectorAll('[id^="seat-"]')
  seatEls.forEach((seatEl, i) => {
    const seatRect = seatEl.getBoundingClientRect()
    const chip = createFloatingChip(seatRect.left + seatRect.width / 2, seatRect.top + seatRect.height / 2)
    gsap.to(chip, {
      left: potRect.left + potRect.width / 2 - 10,
      top: potRect.top + potRect.height / 2 - 10,
      duration: 0.45,
      ease: 'power2.in',
      delay: i * 0.04,
      onComplete: () => chip.remove(),
    })
  })
}

function animatePotToSeat(winnerSeat: number, tokenCount: number, _potAmount: number) {
  const potEl = document.getElementById('pot-display')
  const seatEl = document.getElementById(`seat-${winnerSeat}`)
  if (!potEl || !seatEl) return

  const potRect = potEl.getBoundingClientRect()
  const seatRect = seatEl.getBoundingClientRect()

  for (let i = 0; i < tokenCount; i++) {
    const chip = createFloatingChip(potRect.left + potRect.width / 2, potRect.top + potRect.height / 2)
    const denom = CHIP_DENOMINATIONS[i % CHIP_DENOMINATIONS.length]
    chip.style.backgroundColor = denom.color

    gsap.to(chip, {
      left: seatRect.left + seatRect.width / 2 - 10 + (Math.random() - 0.5) * 20,
      top: seatRect.top + seatRect.height / 2 - 10 + (Math.random() - 0.5) * 20,
      duration: 0.55,
      ease: 'power2.out',
      delay: i * 0.04,
      onComplete: () => chip.remove(),
    })
  }
}

function createFloatingChip(x: number, y: number): HTMLElement {
  const chip = document.createElement('div')
  chip.style.cssText = `
    position: fixed;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background-color: #f9fafb;
    border: 2px solid rgba(0,0,0,0.3);
    left: ${x - 10}px;
    top: ${y - 10}px;
    pointer-events: none;
    z-index: 9999;
    box-shadow: 0 2px 4px rgba(0,0,0,0.4);
  `
  document.body.appendChild(chip)
  return chip
}
