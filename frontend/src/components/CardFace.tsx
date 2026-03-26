import { motion } from 'framer-motion'
import type { Card } from '@/types'
import { getSuitColor, getSuitSymbol, getRankDisplay } from '@/utils/gameUtils'

interface CardFaceProps {
  card: Card
  size?: 'sm' | 'md' | 'lg'
  ghost?: boolean
  highlighted?: boolean
  className?: string
}

const SIZE_MAP = {
  sm: { w: 32, h: 44, rank: 'text-sm', suit: 'text-xs' },
  md: { w: 44, h: 62, rank: 'text-base', suit: 'text-sm' },
  lg: { w: 60, h: 84, rank: 'text-xl', suit: 'text-base' },
}

export default function CardFace({ card, size = 'md', ghost = false, highlighted = false, className = '' }: CardFaceProps) {
  const dims = SIZE_MAP[size]
  const color = getSuitColor(card.suit)
  const suit = getSuitSymbol(card.suit)
  const rank = getRankDisplay(card.rank)

  return (
    <div
      className={`
        relative rounded-md bg-white border select-none flex flex-col items-center justify-between p-0.5
        ${ghost ? 'ghost-card' : ''}
        ${highlighted ? 'ring-2 ring-yellow-400 shadow-yellow-400/60 shadow-lg' : ''}
        ${className}
      `}
      style={{ width: dims.w, height: dims.h, borderColor: highlighted ? '#facc15' : '#d1d5db' }}
    >
      {/* Top-left rank + suit */}
      <div className="self-start leading-none" style={{ color }}>
        <div className={`font-bold ${dims.rank} leading-none`}>{rank}</div>
        <div className={`${dims.suit} leading-none`}>{suit}</div>
      </div>

      {/* Center suit */}
      <div className="text-2xl" style={{ color, fontSize: dims.w * 0.45 }}>
        {suit}
      </div>

      {/* Bottom-right rank + suit (rotated) */}
      <div className="self-end leading-none rotate-180" style={{ color }}>
        <div className={`font-bold ${dims.rank} leading-none`}>{rank}</div>
        <div className={`${dims.suit} leading-none`}>{suit}</div>
      </div>
    </div>
  )
}

interface CardBackProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function CardBack({ size = 'md', className = '' }: CardBackProps) {
  const dims = SIZE_MAP[size]
  return (
    <div
      className={`card-back rounded-md flex items-center justify-center select-none ${className}`}
      style={{ width: dims.w, height: dims.h }}
    >
      <div className="rounded-sm border border-blue-300/40" style={{ width: dims.w - 8, height: dims.h - 8 }}>
        <div
          className="w-full h-full rounded-sm"
          style={{
            backgroundImage: 'repeating-linear-gradient(45deg, #1e3a8a 0px, #1e3a8a 2px, transparent 2px, transparent 8px)',
            opacity: 0.5,
          }}
        />
      </div>
    </div>
  )
}

interface AnimatedCardProps {
  card?: Card
  faceDown?: boolean
  size?: 'sm' | 'md' | 'lg'
  ghost?: boolean
  highlighted?: boolean
  delay?: number
  className?: string
  onClick?: () => void
}

export function AnimatedCard({
  card,
  faceDown = false,
  size = 'md',
  ghost = false,
  highlighted = false,
  delay = 0,
  className = '',
  onClick,
}: AnimatedCardProps) {
  return (
    <motion.div
      initial={{ scale: 0, y: -20, opacity: 0 }}
      animate={{ scale: 1, y: 0, opacity: 1 }}
      exit={{ scale: 0, y: -20, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20, delay }}
      onClick={onClick}
      className={onClick ? 'cursor-pointer' : ''}
    >
      {faceDown || !card ? (
        <CardBack size={size} className={className} />
      ) : (
        <CardFace card={card} size={size} ghost={ghost} highlighted={highlighted} className={className} />
      )}
    </motion.div>
  )
}

interface FlipCardProps {
  card: Card
  faceUp: boolean
  size?: 'sm' | 'md' | 'lg'
  ghost?: boolean
  highlighted?: boolean
  onClick?: () => void
}

export function FlipCard({ card, faceUp, size = 'md', ghost = false, highlighted = false, onClick }: FlipCardProps) {
  return (
    <motion.div
      style={{ perspective: 600 }}
      animate={{ rotateY: faceUp ? 0 : 180 }}
      transition={{ duration: 0.4 }}
      onClick={onClick}
      className={onClick ? 'cursor-pointer' : ''}
    >
      {faceUp ? (
        <CardFace card={card} size={size} ghost={ghost} highlighted={highlighted} />
      ) : (
        <CardBack size={size} />
      )}
    </motion.div>
  )
}
