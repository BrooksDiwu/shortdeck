import { gsap } from 'gsap'
import { getChipBreakdown, CHIP_DENOMINATIONS } from '@/utils/gameUtils'

interface ChipStackProps {
  amount: number
  size?: 'sm' | 'md'
  className?: string
  id?: string
}

const CHIP_DIAMETER_SM = 18
const CHIP_DIAMETER_MD = 24
const CHIP_OFFSET = 3 // vertical offset per chip

export default function ChipStack({ amount, size = 'md', className = '', id }: ChipStackProps) {
  if (amount <= 0) return null

  const breakdown = getChipBreakdown(amount)
  const diameter = size === 'sm' ? CHIP_DIAMETER_SM : CHIP_DIAMETER_MD

  // Flatten into individual chip display items (cap per denom for visual)
  const chips: Array<{ color: string }> = []
  for (const { color, count } of breakdown) {
    const shown = Math.min(count, 6) // max 6 per denomination for clean look
    for (let i = 0; i < shown; i++) {
      chips.push({ color })
    }
  }

  const totalHeight = chips.length * CHIP_OFFSET + diameter

  return (
    <div
      id={id}
      className={`chip-stack-container relative inline-flex flex-col items-center ${className}`}
      style={{ width: diameter, height: totalHeight }}
    >
      {chips.map((chip, i) => (
        <div
          key={i}
          className="absolute rounded-full border-2 border-black/30"
          style={{
            width: diameter,
            height: diameter,
            backgroundColor: chip.color,
            bottom: i * CHIP_OFFSET,
            boxShadow: '0 1px 2px rgba(0,0,0,0.4)',
          }}
        />
      ))}
    </div>
  )
}

export function useChipAnimation() {
  const animateChips = (
    fromRect: DOMRect,
    toRect: DOMRect,
    count: number,
    onComplete?: () => void
  ) => {
    const container = document.body
    const chips: HTMLElement[] = []

    for (let i = 0; i < count; i++) {
      const chip = document.createElement('div')
      chip.className = 'fixed rounded-full border-2 border-black/30 pointer-events-none z-50'
      const denom = CHIP_DENOMINATIONS[i % CHIP_DENOMINATIONS.length]
      chip.style.cssText = `
        width: 20px;
        height: 20px;
        background-color: ${denom.color};
        left: ${fromRect.left + fromRect.width / 2 - 10}px;
        top: ${fromRect.top + fromRect.height / 2 - 10}px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.4);
      `
      container.appendChild(chip)
      chips.push(chip)
    }

    const tl = gsap.timeline({
      onComplete: () => {
        chips.forEach((c) => c.remove())
        onComplete?.()
      },
    })

    chips.forEach((chip, i) => {
      tl.to(
        chip,
        {
          left: toRect.left + toRect.width / 2 - 10,
          top: toRect.top + toRect.height / 2 - 10,
          duration: 0.6,
          ease: 'power2.inOut',
          delay: i * 0.05,
        },
        0
      )
    })

    return tl
  }

  return { animateChips }
}
