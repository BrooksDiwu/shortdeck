import { useState, useEffect, useRef } from 'react'

/**
 * Returns a countdown value [0, totalSeconds] that ticks down every second.
 * Resets when `active` transitions from false → true.
 */
export function useTimerCountdown(totalSeconds: number, active: boolean): number {
  const [remaining, setRemaining] = useState(totalSeconds)
  const prevActiveRef = useRef(false)

  useEffect(() => {
    if (!active) {
      prevActiveRef.current = false
      setRemaining(totalSeconds)
      return
    }

    // Reset on new turn
    if (!prevActiveRef.current) {
      setRemaining(totalSeconds)
      prevActiveRef.current = true
    }

    if (remaining <= 0) return

    const interval = setInterval(() => {
      setRemaining((r) => Math.max(0, r - 1))
    }, 1000)

    return () => clearInterval(interval)
  }, [active, remaining, totalSeconds])

  return remaining
}
