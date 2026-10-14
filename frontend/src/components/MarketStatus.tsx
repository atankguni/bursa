import { useMarketStatus } from '../hooks'

// Per-session visual: dot colour, label, whether the dot should pulse.
const SESSIONS = {
  open: { label: 'Open', dot: 'bg-bull', text: 'text-bull', pulse: true },
  pre_open: {
    label: 'Pre-open',
    dot: 'bg-amber-500',
    text: 'text-amber-500',
    pulse: false,
  },
  break: { label: 'Break', dot: 'bg-amber-500', text: 'text-amber-500', pulse: false },
  closed: { label: 'Closed', dot: 'bg-subtle', text: 'text-subtle', pulse: false },
} as const

/** IDX trading-hours indicator for the navbar. */
export default function MarketStatus() {
  const { data } = useMarketStatus()

  if (!data) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] text-subtle ring-1 ring-line">
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
      className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-medium ring-1 ring-line"
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${s.dot} ${s.pulse ? 'animate-pulse' : ''}`}
      />
      <span className={s.text}>BEI {s.label}</span>
    </span>
  )
}
