import { useState, type ReactNode } from 'react'

/**
 * Flashes its background green or red for a moment when `value` moves, so a
 * refresh shows at a glance which prices changed. Nothing on first render, and
 * nothing with Reduce motion (handled in CSS).
 */
export default function PriceFlash({
  value,
  children,
}: {
  value: number | null | undefined
  children: ReactNode
}) {
  const [prev, setPrev] = useState(value)
  const [flash, setFlash] = useState<{ dir: 'up' | 'down'; n: number } | null>(null)
  // Adjusting state while rendering (React's pattern for reacting to a prop change).
  if (value !== prev) {
    setPrev(value)
    if (value != null && prev != null)
      setFlash((f) => ({ dir: value > prev ? 'up' : 'down', n: (f?.n ?? 0) + 1 }))
  }
  return (
    // A new key restarts the animation when the price moves again.
    <span key={flash?.n ?? 0} className={flash ? `price-flash-${flash.dir}` : undefined}>
      {children}
    </span>
  )
}
