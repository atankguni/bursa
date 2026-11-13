import { Mail } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useStatus } from '../hooks'
import { useAuth } from '../lib/auth'
import { fmtTimeAgo } from '../lib/format'

const SESSION_LABEL: Record<string, string> = {
  pre_open: 'Pre-open',
  open: 'Open',
  break: 'Break',
  closed: 'Closed',
}

/** Persistent footer: copyright + data freshness/provenance. */
export default function Footer() {
  const { data } = useStatus()
  const { isAdmin } = useAuth()
  const year = new Date().getFullYear()
  const calls = Object.values(data?.calls_today ?? {}).reduce((a, b) => a + b, 0)
  const provider = data?.providers['price'] ?? 'yahoo'

  return (
    <footer className="border-t border-line px-4 py-3 text-2xs text-subtle sm:px-6 lg:px-8 print:hidden">
      <div className="mx-auto flex w-full max-w-[1680px] flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
        <span className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
          © {year} Atank Guni
          <span aria-hidden>·</span>
          <a
            href="mailto:atankguni@gmail.com"
            className="inline-flex items-center gap-1 transition hover:text-ink"
          >
            <Mail size={11} /> atankguni@gmail.com
          </a>
          <span aria-hidden>·</span>
          <span title="Free and open-source software under the MIT License">
            Open source · MIT
          </span>
          <span aria-hidden>·</span>
          {/* Required attribution for TradingView Lightweight Charts (Apache-2.0). */}
          <a
            href="https://www.tradingview.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="transition hover:text-ink"
          >
            Charts by TradingView
          </a>
        </span>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Link
            to="/glossary"
            className="underline-offset-2 transition hover:text-ink hover:underline"
          >
            What the numbers mean
          </Link>
          {isAdmin && (
            <Link
              to="/data"
              className="underline-offset-2 transition hover:text-ink hover:underline"
            >
              Data health
            </Link>
          )}
          <span>
            Last sync <span className="text-muted">{fmtTimeAgo(data?.last_sync)}</span>
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
