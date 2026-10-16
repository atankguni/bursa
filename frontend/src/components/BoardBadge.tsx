import { ShieldAlert } from 'lucide-react'

/**
 * Warning chip for stocks on IDX's special-monitoring board (Papan Pemantauan
 * Khusus). Renders nothing for other boards.
 */
export default function BoardBadge({
  board,
  compact = false,
}: {
  board?: string | null
  compact?: boolean
}) {
  if (board !== 'Watchlist') return null
  return (
    <span
      title="IDX special monitoring (Papan Pemantauan Khusus): flagged by the exchange, e.g. for very low price or liquidity, negative equity, going-concern issues or suspension. Trades by periodic call auction. Signals are capped at Hold."
      className="inline-flex items-center gap-0.5 rounded-sm bg-amber-500/15 px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-700 ring-1 ring-amber-500/30 dark:text-amber-300"
    >
      <ShieldAlert size={10} aria-hidden />
      {compact ? 'PPK' : 'Special monitoring'}
      {compact && <span className="sr-only"> (special monitoring)</span>}
    </span>
  )
}
