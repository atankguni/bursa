import { useMarketStatus } from '../hooks'

// Per-session visual: dot colour, label, text colour, chip tint.
const SESSIONS = {
  open: {
    label: 'Open',
    dot: 'bg-bull',
    text: 'text-bull',
    chip: 'bg-bull/10 ring-bull/20',
    pulse: true,
  },
  pre_open: {
    label: 'Pre-open',
    dot: 'bg-amber-500',
    text: 'text-amber-600 dark:text-amber-400',
    chip: 'bg-amber-500/10 ring-amber-500/20',
    pulse: false,
  },
  break: {
    label: 'Break',
    dot: 'bg-amber-500',
    text: 'text-amber-600 dark:text-amber-400',
    chip: 'bg-amber-500/10 ring-amber-500/20',
    pulse: false,
  },
  closed: {
    label: 'Closed',
    dot: 'bg-subtle',
    text: 'text-subtle',
    chip: 'bg-panelalt ring-line',
    pulse: false,
  },
} as const

/** IDX trading-hours indicator for the navbar. */
export default function MarketStatus() {
  const { data } = useMarketStatus()

  if (!data) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded bg-panelalt px-2.5 py-1 text-[11px] text-subtle ring-1 ring-line">
        <span className="h-1.5 w-1.5 rounded-full bg-subtle" />
        BEI …
      </span>
    )
  }

  const s = SESSIONS[data.session]
  const time = new Date(data.server_time).toLocaleTimeString('en-GB', {
    timeZone: data.timezone,
    hour: '2-digit',
    minute: '2-digit',
  })
  const tooltip = `IDX ${s.label} · ${time} WIB${data.next_change_label ? ` · ${data.next_change_label}` : ''}`

  return (
    <span
      title={tooltip}
      className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-[11px] font-medium ring-1 ${s.chip}`}
    >
      <span className="relative flex h-1.5 w-1.5">
        {s.pulse && (
          <span
            className={`absolute inline-flex h-full w-full animate-ping rounded-full ${s.dot} opacity-60`}
          />
        )}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${s.dot}`} />
      </span>
      <span className={s.text}>BEI {s.label}</span>
    </span>
  )
}
