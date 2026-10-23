import { useState } from 'react'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { useIndices } from '../hooks'
import { fmtPct, fmtPrice, fmtShortDateTime } from '../lib/format'
import { useSettings } from '../lib/settings'
import IndexChartModal from './IndexChartModal'

/** Navbar chip: IHSG (IDX Composite) value + today's change; click for the chart. */
export default function IhsgTicker() {
  const { data } = useIndices() // same query as the Market page: no extra requests
  const { settings } = useSettings()
  const [open, setOpen] = useState(false)
  const ihsg = data?.find((i) => i.code === 'COMPOSITE')

  if (!ihsg || ihsg.last == null) return null

  const pct = ihsg.change_percent
  const tone =
    !settings.colorizeChanges || pct == null || pct === 0
      ? 'text-muted'
      : pct > 0
        ? 'text-bull'
        : 'text-bear'
  const tooltip = [
    'IDX Composite (IHSG)',
    ihsg.previous_close != null && `prev close ${fmtPrice(ihsg.previous_close)}`,
    ihsg.updated_at && `updated ${fmtShortDateTime(ihsg.updated_at)}`,
    'click for chart',
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title={tooltip}
        aria-label={`IHSG ${fmtPrice(ihsg.last)}${pct != null ? `, ${fmtPct(pct)} today` : ''}. Open chart`}
        className="hidden items-center gap-1.5 rounded-sm bg-panelalt px-2.5 py-1.5 text-xs ring-1 ring-line transition hover:ring-line-strong sm:inline-flex"
      >
        <span className="font-semibold text-muted">IHSG</span>
        <span className="font-semibold tabular-nums text-ink">{fmtPrice(ihsg.last)}</span>
        {pct != null && (
          <span className={`inline-flex items-center font-medium tabular-nums ${tone}`}>
            {pct >= 0 ? (
              <ArrowUpRight size={12} aria-hidden />
            ) : (
              <ArrowDownRight size={12} aria-hidden />
            )}
            {fmtPct(pct)}
          </span>
        )}
      </button>
      {open && <IndexChartModal index={ihsg} onClose={() => setOpen(false)} />}
    </>
  )
}
