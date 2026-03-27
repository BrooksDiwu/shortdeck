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
const CHIP_OFFSET = 3 // vertical offset per chip in a column

const CHIPS_PER_STACK = 20 // each visual stack represents this many chips

// Grid sequence: add a row first, then a column.
// 1 stack=1×1, 2=1×2, 3-4=2×2, 5-6=2×3, 7-9=3×3, ...
function getGrid(numStacks: number): [number, number] {
  let cols = 1, rows = 1
  while (cols * rows < numStacks) {
    if (rows === cols) rows++
    else cols++
  }
  return [cols, rows]
}

// Renders a single physical stack of chips showing denomination colors bottom-to-top.
// `chips` is an ordered array of colors from bottom chip to top chip.
function SingleStack({ chips, diameter }: { chips: string[]; diameter: number }) {
  const height = chips.length * CHIP_OFFSET + diameter
  return (
    <div className="relative flex-shrink-0" style={{ width: diameter, height }}>
      {chips.map((color, i) => (
        <div
          key={i}
          className="absolute rounded-full border-2 border-black/30"
          style={{
            width: diameter,
            height: diameter,
            backgroundColor: color,
            bottom: i * CHIP_OFFSET,
            boxShadow: '0 1px 2px rgba(0,0,0,0.4)',
          }}
        />
      ))}
    </div>
  )
}

export default function ChipStack({ amount, size = 'md', className = '', id }: ChipStackProps) {
  if (amount <= 0) return null

  const breakdown = getChipBreakdown(amount)
  const diameter = size === 'sm' ? CHIP_DIAMETER_SM : CHIP_DIAMETER_MD

  // Total number of physical chips across all denominations
  const totalChips = breakdown.reduce((s, { count }) => s + count, 0)
  // Each grid cell = one visual stack representing CHIPS_PER_STACK real chips
  const numStacks = Math.max(1, Math.ceil(totalChips / CHIPS_PER_STACK))
  const [numCols, numRows] = getGrid(numStacks)

  // Build the color sequence for a single representative stack (denomination colors,
  // proportional to their share of the total). Every stack cell shows the same pattern.
  const STACK_CHIP_COUNT = 8 // how many colored chips to show per visual stack
  const stackChips: string[] = []
  for (const { color, count } of breakdown) {
    const slots = Math.max(1, Math.round((count / totalChips) * STACK_CHIP_COUNT))
    for (let i = 0; i < slots && stackChips.length < STACK_CHIP_COUNT; i++) {
      stackChips.push(color)
    }
  }
  // Pad to STACK_CHIP_COUNT if rounding left us short
  while (stackChips.length < STACK_CHIP_COUNT) stackChips.push(breakdown[breakdown.length - 1].color)

  // Each grid cell is one SingleStack. Cells are arranged:
  //   cols = side by side horizontally (x-axis)
  //   rows = stacks offset slightly behind each other (z-depth illusion via y-offset)
  // We render rows back-to-front so front row appears on top.
  const singleStackHeight = STACK_CHIP_COUNT * CHIP_OFFSET + diameter
  const ROW_DEPTH_OFFSET = 4 // px each row shifts down to give depth illusion
  const totalHeight = singleStackHeight + (numRows - 1) * ROW_DEPTH_OFFSET
  const totalWidth = numCols * (diameter + 4) - 4

  return (
    <div
      id={id}
      className={`chip-stack-container relative ${className}`}
      style={{ width: totalWidth, height: totalHeight }}
    >
      {Array.from({ length: numRows }).map((_, ri) =>
        Array.from({ length: numCols }).map((_, ci) => {
          const stackIdx = ri * numCols + ci
          if (stackIdx >= numStacks) return null
          return (
            <div
              key={`${ri}-${ci}`}
              className="absolute"
              style={{
                left: ci * (diameter + 4),
                top: (numRows - 1 - ri) * ROW_DEPTH_OFFSET,
              }}
            >
              <SingleStack chips={stackChips} diameter={diameter} />
            </div>
          )
        })
      )}
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
