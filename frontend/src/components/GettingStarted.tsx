import { Link } from 'react-router-dom'
import { Check, ChevronRight, X } from 'lucide-react'
import { DEFAULT_COSTS, usePreferences, useTransactions, useWatchlist } from '../hooks'
import { useAuth } from '../lib/auth'
import { isBool, useStoredState } from '../lib/storedState'

interface Step {
  id: string
  title: string
  hint: string
  to: string
  done: boolean
}

/**
 * First steps for a new account, on Home. Each step ticks itself off from what
 * the account has done; the card goes away once all are done, or when dismissed.
 */
export default function GettingStarted() {
  const { user } = useAuth()
  const { data: watchlist, isSuccess: watchLoaded } = useWatchlist()
  const { data: txs, isSuccess: txsLoaded } = useTransactions()
  const { tradingCosts } = usePreferences()
  const [dismissed, setDismissed] = useStoredState(
    'home.gettingStarted.dismissed',
    false,
    isBool,
  )
  // The fees can't be told "set" when they equal the defaults: opening them counts.
  const [feesSeen, setFeesSeen] = useStoredState(
    'home.gettingStarted.fees',
    false,
    isBool,
  )

  if (dismissed || !user || !watchLoaded || !txsLoaded) return null

  const feesChanged = (['buy_fee_pct', 'sell_fee_pct', 'dividend_tax_pct'] as const).some(
    (k) => tradingCosts[k] !== DEFAULT_COSTS[k],
  )
  const steps: Step[] = [
    {
      id: 'watch',
      title: 'Follow a stock',
      hint: 'Tap + on a stock below, or the star in its detail window.',
      to: '/browse',
      done: watchlist.length > 0,
    },
    {
      id: 'tx',
      title: 'Record what you own',
      hint: 'Add a buy from your broker statement to see your profit and dividends.',
      to: '/portfolio',
      done: txs.length > 0,
    },
    {
      id: 'fees',
      title: "Check your broker's fees",
      hint: 'Used for profit after costs and the sell calculator.',
      to: '/settings/investing',
      done: feesChanged || feesSeen,
    },
    {
      id: '2fa',
      title: 'Turn on two-factor sign-in',
      hint: 'A code from your phone, so a stolen password alone is not enough.',
      to: '/settings/security',
      done: user.has_2fa,
    },
  ]
  const doneCount = steps.filter((s) => s.done).length
  if (doneCount === steps.length) return null

  return (
    <section className="surface mb-6 p-4 sm:p-5" aria-labelledby="getting-started-title">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 id="getting-started-title" className="section-title">
            Get started with Bursa
          </h3>
          <p className="text-2xs text-subtle">
            {doneCount} of {steps.length} done
          </p>
        </div>
        <button
          onClick={() => setDismissed(true)}
          aria-label="Hide getting started"
          title="Hide"
          className="btn btn-ghost btn-icon -mt-1 -mr-1"
        >
          <X size={16} />
        </button>
      </div>
      <div
        className="mt-3 h-1 overflow-hidden rounded-full bg-panelalt"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={steps.length}
        aria-valuenow={doneCount}
        aria-label="Getting started progress"
      >
        <div
          className="h-full rounded-full bg-accent transition-[width]"
          style={{ width: `${(doneCount / steps.length) * 100}%` }}
        />
      </div>
      <ol className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((s) => (
          <li key={s.id}>
            <Link
              to={s.to}
              onClick={() => s.id === 'fees' && setFeesSeen(true)}
              className={`group flex h-full items-start gap-3 rounded-md px-3 py-2.5 transition-colors ${
                s.done ? 'opacity-60' : 'bg-panelalt/60 hover:bg-panelalt'
              }`}
            >
              <span
                className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full ${
                  s.done ? 'bg-accent text-accent-ink' : 'ring-1 ring-line-strong'
                }`}
                aria-hidden
              >
                {s.done && <Check size={12} strokeWidth={3} />}
              </span>
              <span className="min-w-0 flex-1">
                <span
                  className={`block text-xs font-medium ${s.done ? 'text-muted line-through' : 'text-ink'}`}
                >
                  {s.title}
                  <span className="sr-only">{s.done ? ' (done)' : ''}</span>
                </span>
                {!s.done && (
                  <span className="mt-0.5 block text-2xs text-muted">{s.hint}</span>
                )}
              </span>
              {!s.done && (
                <ChevronRight
                  size={14}
                  className="mt-0.5 shrink-0 text-subtle transition-transform group-hover:translate-x-0.5"
                  aria-hidden
                />
              )}
            </Link>
          </li>
        ))}
      </ol>
    </section>
  )
}
