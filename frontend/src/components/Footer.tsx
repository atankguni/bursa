import { Mail } from 'lucide-react'
import { useStatus } from '../hooks'

const SESSION_LABEL: Record<string, string> = {
  pre_open: 'Pre-open',
  open: 'Open',
  break: 'Break',
  closed: 'Closed',
}

function timeAgo(iso: string | null): string {
  if (!iso) return '—'
  const then = new Date(`${iso}Z`).getTime()
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000))
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

/** Persistent footer: copyright + data freshness/provenance. */
export default function Footer() {
  const { data } = useStatus()
  const year = new Date().getFullYear()
  const calls = Object.values(data?.calls_today ?? {}).reduce((a, b) => a + b, 0)
  const provider = data?.providers?.price ?? 'yahoo'

  return (
    <footer className="border-t border-line bg-panel/80 px-4 py-2 text-[11px] text-subtle">
      <div className="flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <span className="inline-flex items-center gap-1.5">
          © {year} Lalu Haryadi Guni
          <span aria-hidden>·</span>
          <a
            href="mailto:atankguni@gmail.com"
            className="inline-flex items-center gap-1 transition hover:text-ink"
          >
            <Mail size={11} /> atankguni@gmail.com
          </a>
        </span>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>
            Last sync{' '}
            <span className="text-muted">{timeAgo(data?.last_sync ?? null)}</span>
          </span>
          <span>
            BEI{' '}
            <span className="text-muted">
              {SESSION_LABEL[data?.session ?? ''] ?? '—'}
            </span>
          </span>
          <span>
            Data <span className="text-muted">{provider}</span>
          </span>
          <span>
            <span className="text-muted">{calls}</span> calls today
          </span>
          <span>
            <span className="text-muted">{data?.stocks_tracked ?? '—'}</span> tracked
          </span>
        </div>
      </div>
    </footer>
  )
}
