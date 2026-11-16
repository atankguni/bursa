import { lazy, Suspense, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Briefcase,
  Eye,
  EyeOff,
  FileText,
  LineChart,
  NotebookPen,
  Plus,
  ReceiptText,
  Trash2,
} from 'lucide-react'
import { deleteTransaction } from '../api'
import {
  useCash,
  useMediaQuery,
  useNotes,
  usePortfolio,
  usePortfolioHistory,
  benchmarkLabel,
  usePreferences,
  useStatus,
  useTransactions,
} from '../hooks'
import { useHideValuesOnOpen, useSettings } from '../lib/settings'
import { estimateSale } from '../lib/sellEstimate'
import { fmtMoney, fmtMoneySigned, fmtNum, fmtPrice } from '../lib/format'
import BoardBadge from '../components/BoardBadge'
import BuyCalculator from '../components/BuyCalculator'
import NoteModal, { FLAG_TEXT } from '../components/NoteModal'
import CashPanel from '../components/CashPanel'
import DividendCalendar from '../components/DividendCalendar'
import DividendIncomeChart from '../components/DividendIncomeChart'
import RiskPanel from '../components/RiskPanel'
import SellCalculator from '../components/SellCalculator'
import SubTabs from '../components/SubTabs'
import TransactionModal from '../components/TransactionModal'
import EmptyState from '../components/ui/EmptyState'
import PageHeader from '../components/ui/PageHeader'
import { SkeletonCard, SkeletonRows } from '../components/ui/Skeleton'
import Stat from '../components/ui/Stat'
import type { Holding, HoldingNote } from '../api'
import PriceFlash from '../components/ui/PriceFlash'
import { useToast } from '../lib/toast'

const PortfolioChart = lazy(() => import('../components/PortfolioChart'))

const signedPct = (v: number | null | undefined) =>
  v == null ? '—' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmtNum(Math.abs(v), 2)}%`

// IDX lots: shares / lotSize (integer when whole).
const lotsOf = (shares: number, lotSize: number) => {
  const v = shares / lotSize
  return fmtNum(v, 0, 2)
}

/**
 * Privacy mask: when hidden, the real value is not rendered at all (not just
 * blurred), so it can't leak via screen share, zoom, selection or copy/paste.
 */
const MASK = '••••••'
function Secret({ hidden, children }: { hidden: boolean; children: ReactNode }) {
  return hidden ? (
    <span aria-label="hidden" className="select-none tracking-widest">
      {MASK}
    </span>
  ) : (
    <>{children}</>
  )
}

const TABS = ['holdings', 'cash', 'income', 'risk', 'activity'] as const
type Tab = (typeof TABS)[number]
const isTab = (v: string | null): v is Tab => TABS.some((t) => t === v)

export default function Portfolio() {
  const [adding, setAdding] = useState(false)
  const [selling, setSelling] = useState<Holding | null>(null)
  const [buying, setBuying] = useState<Holding | null>(null)
  const [noting, setNoting] = useState<string | null>(null)
  const [recording, setRecording] = useState<{
    side: 'buy' | 'sell'
    ticker: string
    lots: number
    price: number
  } | null>(null)
  const [params, setParams] = useSearchParams()
  const raw = params.get('tab')
  const tab: Tab = isTab(raw) ? raw : 'holdings'
  const setTab = (t: Tab) =>
    setParams(t === 'holdings' ? {} : { tab: t }, { replace: true })

  const { tradingCosts, benchmark } = usePreferences()
  const bench = benchmarkLabel(benchmark)
  const qc = useQueryClient()
  const { settings, update } = useSettings()
  useHideValuesOnOpen()
  const hide = settings.hidePortfolioValues
  const { data: pf, isLoading } = usePortfolio()
  const { data: txs = [] } = useTransactions()
  const { data: history = [] } = usePortfolioHistory()
  const { data: cash } = useCash()
  const { data: status } = useStatus()
  const lotSize = status?.lot_size ?? 100
  // The chart fills the hero's height beside the figures on wide screens.
  const chartHeight = useMediaQuery('(min-width: 64rem)') ? 380 : 240

  const { deleteWithUndo, isDeleting } = useToast()
  const removeTx = (t: (typeof txs)[number]) =>
    deleteWithUndo({
      key: `tx:${t.id}`,
      label: `${t.ticker} ${t.kind === 'trade' ? t.side : t.kind}`,
      commit: () => deleteTransaction(t.id),
      onDone: () => qc.invalidateQueries({ queryKey: ['portfolio'] }),
    })

  const tone = (v: number | null | undefined) => {
    if (!settings.colorizeChanges || v == null || v === 0) return 'text-muted'
    return v > 0 ? 'text-bull' : 'text-bear'
  }
  const pill = (v: number | null | undefined) => {
    if (!settings.colorizeChanges || v == null || v === 0) return 'bg-panelalt text-muted'
    return v > 0 ? 'bg-bull/10 text-bull' : 'bg-bear/10 text-bear'
  }

  const [chartMode, setChartMode] = useState<'value' | 'return'>('value')
  // Latest time-weighted return vs the benchmark over the same period.
  const lastPoint = [...history]
    .reverse()
    .flatMap((p) =>
      p.return_pct != null && p.benchmark_pct != null
        ? [{ mine: p.return_pct, ihsg: p.benchmark_pct }]
        : [],
    )[0]
  const firstPoint = history[0]
  const versus = lastPoint && firstPoint ? { since: firstPoint.date, ...lastPoint } : null

  const totals = pf?.totals
  const holdings = pf?.holdings ?? []
  const { data: notes = [] } = useNotes()
  const noteBy = new Map(notes.map((n) => [n.ticker, n]))
  const held = new Set(holdings.map((h) => h.ticker))
  const attention = notes.filter((n) => n.flags.length > 0 && held.has(n.ticker))
  const tracked = cash?.tracked ?? false
  const money = (v: number | null | undefined) => (
    <Secret hidden={hide}>{fmtMoney(v)}</Secret>
  )
  const moneySigned = (v: number | null | undefined) => (
    <Secret hidden={hide}>{fmtMoneySigned(v)}</Secret>
  )

  return (
    <main className="page">
      <PageHeader
        title="Portfolio"
        subtitle={`${holdings.length} position${holdings.length === 1 ? '' : 's'} · average-cost P/L`}
        actions={
          <>
            <button
              onClick={() => update({ hidePortfolioValues: !hide })}
              aria-pressed={hide}
              title={hide ? 'Show amounts' : 'Hide amounts (for screen sharing)'}
              className={`btn btn-ghost ${hide ? 'bg-panelalt text-ink' : ''}`}
            >
              {hide ? <EyeOff size={15} /> : <Eye size={15} />}
              <span className="hidden sm:inline">
                {hide ? 'Show values' : 'Hide values'}
              </span>
            </button>
            <Link
              to="/portfolio/tax"
              title="Holdings on 31 December, dividends and sales for your SPT"
              className="btn btn-secondary"
            >
              <FileText size={15} /> Tax summary
            </Link>
            <button onClick={() => setAdding(true)} className="btn btn-primary">
              <Plus size={15} /> Add transaction
            </button>
          </>
        }
      />

      {isLoading ? (
        <div className="space-y-4">
          <SkeletonCard className="h-64" />
          <div className="surface">
            <SkeletonRows />
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Hero: the headline number, the supporting figures, the chart. */}
          <section className="surface overflow-hidden">
            <div className="grid lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
              <div className="border-b border-line p-5 sm:p-6 lg:border-r lg:border-b-0">
                <Stat
                  size="hero"
                  label={tracked ? 'Account value' : 'Market value'}
                  value={money(tracked ? cash?.account_value : totals?.market_value)}
                  title={tracked ? 'Shares at the last price + cash' : undefined}
                />
                <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium tabular-nums">
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 ${pill(totals?.day_change)}`}
                  >
                    {moneySigned(totals?.day_change)}
                    <span className="opacity-80">
                      ({signedPct(totals?.day_change_pct)}) today
                    </span>
                  </span>
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 ${pill(totals?.total_return)}`}
                    title="P/L after selling costs + realized + dividends"
                  >
                    {moneySigned(totals?.total_return)}
                    <span className="opacity-80">total return</span>
                  </span>
                </div>

                <div className="mt-6 grid grid-cols-2 gap-x-4 gap-y-5">
                  <Stat label="Invested" value={money(totals?.invested)} />
                  <Stat
                    label="Unrealized P/L"
                    value={moneySigned(totals?.unrealized_pl)}
                    tone={tone(totals?.unrealized_pl)}
                    sub={
                      <>
                        {signedPct(totals?.unrealized_pl_pct)} · after selling costs{' '}
                        <Secret hidden={hide}>
                          {fmtMoneySigned(
                            (totals?.unrealized_pl ?? 0) - (totals?.exit_costs ?? 0),
                          )}
                        </Secret>
                      </>
                    }
                  />
                  <Stat
                    label="Realized P/L"
                    value={moneySigned(totals?.realized_pl)}
                    tone={tone(totals?.realized_pl)}
                  />
                  <Stat
                    label="Dividends received"
                    value={money(totals?.dividends_received)}
                    sub="After tax"
                  />
                  {tracked && (
                    <Stat
                      label="Cash available"
                      value={money(cash?.available)}
                      tone={(cash?.available ?? 0) < 0 ? 'text-bear' : 'text-ink'}
                      sub={
                        cash && cash.settling > 0 ? (
                          <>
                            + <Secret hidden={hide}>{fmtMoney(cash.settling)}</Secret>{' '}
                            settling
                          </>
                        ) : undefined
                      }
                    />
                  )}
                  <Stat
                    label="Est. annual income"
                    value={money(totals?.projected_income)}
                    sub="Last 12 months' dividends"
                  />
                </div>
              </div>

              <div className="flex min-w-0 flex-col p-4 sm:p-5">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="section-title">
                    {chartMode === 'value'
                      ? 'Value over time'
                      : `Your return vs ${bench}`}
                  </div>
                  <div className="segmented" role="group" aria-label="Chart">
                    {(['value', 'return'] as const).map((m) => (
                      <button
                        key={m}
                        onClick={() => setChartMode(m)}
                        aria-pressed={chartMode === m}
                        className="segment"
                      >
                        {m === 'value' ? 'Value' : `vs ${bench}`}
                      </button>
                    ))}
                  </div>
                </div>
                {chartMode === 'return' && versus && (
                  <p className="mb-3 text-xs text-muted">
                    Since {versus.since}: you{' '}
                    <span className={`font-semibold ${tone(versus.mine)}`}>
                      {signedPct(versus.mine)}
                    </span>
                    , {bench}{' '}
                    <span className={`font-semibold ${tone(versus.ihsg)}`}>
                      {signedPct(versus.ihsg)}
                    </span>
                    : {versus.mine >= versus.ihsg ? 'ahead by' : 'behind by'}{' '}
                    <span className="font-semibold text-ink">
                      {fmtNum(Math.abs(versus.mine - versus.ihsg), 2)} pts
                    </span>
                    <span className="text-subtle">
                      {' '}
                      · time-weighted, dividends included; {bench} is price only
                    </span>
                  </p>
                )}
                {history.length > 1 ? (
                  <Suspense
                    fallback={
                      <div className="skeleton" style={{ height: chartHeight }} />
                    }
                  >
                    <PortfolioChart
                      data={history}
                      hideValues={hide}
                      mode={chartMode}
                      height={chartHeight}
                    />
                  </Suspense>
                ) : (
                  <div className="grid flex-1 place-items-center">
                    <EmptyState icon={LineChart} title="Your chart starts here">
                      It fills in day by day once you hold shares.
                    </EmptyState>
                  </div>
                )}
              </div>
            </div>
          </section>

          {attention.length > 0 && (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md bg-amber-500/10 px-4 py-3 text-xs text-amber-800 ring-1 ring-amber-500/20 dark:text-amber-300">
              <NotebookPen size={14} className="shrink-0" />
              <span className="font-medium">Time to look again:</span>
              {attention.map((n, i) => (
                <span key={n.ticker}>
                  {i > 0 && <span className="mr-2 opacity-50">·</span>}
                  <button
                    onClick={() => setNoting(n.ticker)}
                    className="font-semibold underline-offset-2 hover:underline"
                  >
                    {n.ticker}
                  </button>{' '}
                  <span className="opacity-80">
                    ({n.flags.map((f) => FLAG_TEXT[f]).join(', ')})
                  </span>
                </span>
              ))}
            </div>
          )}

          <div>
            <SubTabs<Tab>
              value={tab}
              onChange={setTab}
              options={[
                {
                  value: 'holdings',
                  label: `Holdings${holdings.length ? ` · ${holdings.length}` : ''}`,
                },
                { value: 'cash', label: 'Cash' },
                { value: 'income', label: 'Income' },
                { value: 'risk', label: 'Risk' },
                {
                  value: 'activity',
                  label: `Activity${txs.length ? ` · ${txs.length}` : ''}`,
                },
              ]}
            />
            <div className="mt-4">
              {tab === 'holdings' && (
                <div className="surface overflow-hidden">
                  {holdings.length === 0 ? (
                    <EmptyState
                      icon={Briefcase}
                      title="No positions yet"
                      action={
                        <button
                          onClick={() => setAdding(true)}
                          className="btn btn-primary"
                        >
                          <Plus size={15} /> Add your first transaction
                        </button>
                      }
                    >
                      Record a buy, and Bursa tracks its value, P/L, dividends and risk.
                    </EmptyState>
                  ) : (
                    <div className="relative overflow-x-auto">
                      <table className="w-full text-left text-xs whitespace-nowrap">
                        <thead className="table-head">
                          <tr>
                            <th scope="col" className="px-4 py-3">
                              Stock
                            </th>
                            <th scope="col" className="px-4 py-3 text-right">
                              Lots
                            </th>
                            <th scope="col" className="px-4 py-3 text-right">
                              Avg cost
                            </th>
                            <th scope="col" className="px-4 py-3 text-right">
                              Price
                            </th>
                            <th scope="col" className="px-4 py-3 text-right">
                              Value
                            </th>
                            <th scope="col" className="px-4 py-3 text-right">
                              P/L
                            </th>
                            <th scope="col" className="px-4 py-3 text-right">
                              Today
                            </th>
                            <th scope="col" className="px-4 py-3">
                              Weight
                            </th>
                            <th scope="col" className="px-4 py-3 text-right">
                              Est. income
                            </th>
                            <th
                              scope="col"
                              className="px-4 py-3 text-right"
                              title="Cash you would receive selling all whole lots at the last price, after the sell fee and tax"
                            >
                              Net if sold
                            </th>
                            <th scope="col" className="px-4 py-3">
                              <span className="sr-only">Actions</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-line">
                          {holdings.map((h) => (
                            <tr
                              key={h.ticker}
                              className="group bg-panel transition-colors hover:bg-panelalt/50"
                            >
                              <td className="px-4 py-3">
                                <span className="flex items-center gap-1.5">
                                  <span className="font-semibold text-ink">
                                    {h.ticker}
                                  </span>
                                  <BoardBadge board={h.board} compact />
                                  <NoteButton
                                    note={noteBy.get(h.ticker)}
                                    onClick={() => setNoting(h.ticker)}
                                  />
                                  {h.split_adjusted && (
                                    <span
                                      title="Adjusted for a stock split: shares × ratio and price ÷ ratio, so invested capital is unchanged."
                                      className="rounded-xs bg-panelalt px-1 py-0.5 text-2xs text-muted"
                                    >
                                      split-adj.
                                    </span>
                                  )}
                                </span>
                                <span className="block max-w-[14rem] truncate text-2xs text-subtle">
                                  {h.name}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-right tabular-nums">
                                <Secret hidden={hide}>
                                  <span className="font-medium">
                                    {lotsOf(h.quantity, lotSize)}
                                  </span>
                                  <span className="block text-2xs text-subtle">
                                    {fmtNum(h.quantity)} sh
                                  </span>
                                </Secret>
                              </td>
                              <td className="px-4 py-3 text-right text-muted tabular-nums">
                                <Secret hidden={hide}>{fmtPrice(h.avg_cost)}</Secret>
                              </td>
                              <td className="px-4 py-3 text-right tabular-nums">
                                <PriceFlash value={h.price}>
                                  {fmtPrice(h.price)}
                                </PriceFlash>
                              </td>
                              <td className="px-4 py-3 text-right font-medium tabular-nums">
                                {money(h.market_value)}
                              </td>
                              <td
                                className={`px-4 py-3 text-right tabular-nums ${tone(h.unrealized_pl)}`}
                              >
                                {moneySigned(h.unrealized_pl)}
                                <span className="block text-2xs opacity-80">
                                  {signedPct(h.unrealized_pl_pct)}
                                </span>
                              </td>
                              <td
                                className={`px-4 py-3 text-right tabular-nums ${tone(h.day_change)}`}
                              >
                                {signedPct(h.day_change_pct)}
                              </td>
                              <td className="px-4 py-3">
                                {h.weight != null ? (
                                  <span className="flex items-center gap-2">
                                    <span className="h-1.5 w-14 overflow-hidden rounded-full bg-panelalt">
                                      <span
                                        className="block h-full rounded-full bg-accent/70"
                                        style={{ width: `${Math.min(h.weight, 100)}%` }}
                                      />
                                    </span>
                                    <span className="text-muted tabular-nums">
                                      {fmtNum(h.weight, 1)}%
                                    </span>
                                  </span>
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td className="px-4 py-3 text-right text-muted tabular-nums">
                                {h.projected_income ? money(h.projected_income) : '—'}
                              </td>
                              <td className="px-4 py-3 text-right font-medium tabular-nums">
                                {h.price != null
                                  ? money(
                                      estimateSale({
                                        shares:
                                          Math.floor(h.quantity / lotSize) * lotSize,
                                        price: h.price,
                                        avgCost: h.avg_cost,
                                        sellFeePct: tradingCosts.sell_fee_pct,
                                      }).net,
                                    )
                                  : '—'}
                              </td>
                              <td className="px-4 py-3 text-right">
                                <span className="inline-flex gap-1.5">
                                  <button
                                    onClick={() => setBuying(h)}
                                    title="Buy more: new average cost and break-even price"
                                    className="btn btn-secondary btn-sm"
                                  >
                                    Buy
                                  </button>
                                  <button
                                    onClick={() => setSelling(h)}
                                    title="What selling would bring in, after fees and tax"
                                    className="btn btn-secondary btn-sm"
                                  >
                                    Sell
                                  </button>
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {tab === 'cash' && <CashPanel hide={hide} />}
              {tab === 'income' && (
                <div className="space-y-4">
                  <DividendIncomeChart hideValues={hide} />
                  <DividendCalendar hideValues={hide} />
                </div>
              )}
              {tab === 'risk' &&
                (holdings.length > 0 ? (
                  <RiskPanel enabled />
                ) : (
                  <div className="surface">
                    <EmptyState icon={Briefcase} title="Nothing to measure yet">
                      Risk (concentration, volatility, drawdown) appears once you hold
                      shares.
                    </EmptyState>
                  </div>
                ))}

              {tab === 'activity' && (
                <div className="surface overflow-hidden">
                  {txs.length === 0 ? (
                    <EmptyState icon={ReceiptText} title="No transactions yet">
                      Buys, sales, rights issues and bonus shares you record appear here.
                    </EmptyState>
                  ) : (
                    <div className="relative overflow-x-auto">
                      <table className="w-full text-left text-xs whitespace-nowrap">
                        <thead className="table-head">
                          <tr>
                            <th scope="col" className="px-4 py-3">
                              Date
                            </th>
                            <th scope="col" className="px-4 py-3">
                              Stock
                            </th>
                            <th scope="col" className="px-4 py-3">
                              Type
                            </th>
                            <th scope="col" className="px-4 py-3 text-right">
                              Lots
                            </th>
                            <th scope="col" className="px-4 py-3 text-right">
                              Price
                            </th>
                            <th scope="col" className="px-4 py-3 text-right">
                              Fees
                            </th>
                            <th scope="col" className="w-full px-4 py-3">
                              Note
                            </th>
                            <th scope="col" className="px-4 py-3">
                              <span className="sr-only">Delete</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-line">
                          {txs
                            .filter((t) => !isDeleting(`tx:${t.id}`))
                            .map((t) => (
                              <tr
                                key={t.id}
                                className="bg-panel transition-colors hover:bg-panelalt/50"
                              >
                                <td className="px-4 py-2.5 text-muted tabular-nums">
                                  {t.trade_date}
                                </td>
                                <td className="px-4 py-2.5 font-semibold">{t.ticker}</td>
                                <td className="px-4 py-2.5">
                                  <span
                                    className={`rounded-full px-2 py-0.5 text-2xs font-medium capitalize ${
                                      t.kind !== 'trade'
                                        ? 'bg-accent/10 text-accent'
                                        : t.side === 'buy'
                                          ? 'bg-bull/10 text-bull'
                                          : 'bg-bear/10 text-bear'
                                    }`}
                                  >
                                    {t.kind === 'trade' ? t.side : t.kind}
                                  </span>
                                </td>
                                <td className="px-4 py-2.5 text-right tabular-nums">
                                  <Secret hidden={hide}>
                                    {lotsOf(t.quantity, lotSize)}
                                    <span className="ml-1 text-2xs text-subtle">
                                      ({fmtNum(t.quantity)})
                                    </span>
                                  </Secret>
                                </td>
                                <td className="px-4 py-2.5 text-right tabular-nums">
                                  {t.kind === 'bonus' ? (
                                    <span className="text-subtle">free</span>
                                  ) : (
                                    <Secret hidden={hide}>{fmtPrice(t.price)}</Secret>
                                  )}
                                </td>
                                <td className="px-4 py-2.5 text-right text-subtle tabular-nums">
                                  {t.fees ? money(t.fees) : '—'}
                                </td>
                                <td className="max-w-[20rem] truncate px-4 py-2.5 text-subtle">
                                  {t.note ? <Secret hidden={hide}>{t.note}</Secret> : ''}
                                </td>
                                <td className="px-2 py-1 text-right">
                                  <button
                                    onClick={() => removeTx(t)}
                                    aria-label={`Delete ${t.ticker} transaction of ${t.trade_date}`}
                                    className="btn btn-ghost btn-icon hover:text-bear"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {adding && <TransactionModal onClose={() => setAdding(false)} />}
      {selling && (
        <SellCalculator
          holding={selling}
          onClose={() => setSelling(null)}
          onRecord={(sale) => {
            setRecording({ side: 'sell', ticker: selling.ticker, ...sale })
            setSelling(null)
          }}
        />
      )}
      {buying && (
        <BuyCalculator
          holding={buying}
          onClose={() => setBuying(null)}
          onRecord={(buy) => {
            setRecording({ side: 'buy', ticker: buying.ticker, ...buy })
            setBuying(null)
          }}
        />
      )}
      {noting && (
        <NoteModal
          ticker={noting}
          note={noteBy.get(noting)}
          price={holdings.find((h) => h.ticker === noting)?.price ?? null}
          onClose={() => setNoting(null)}
        />
      )}
      {recording && (
        <TransactionModal initial={recording} onClose={() => setRecording(null)} />
      )}
    </main>
  )
}

/** Opens the holding's note: plain when empty, accent with a note, amber when it needs a look. */
function NoteButton({
  note,
  onClick,
}: {
  note: HoldingNote | undefined
  onClick: () => void
}) {
  const flagged = (note?.flags.length ?? 0) > 0
  return (
    <button
      onClick={onClick}
      aria-label={note ? 'Open your note' : 'Add a note'}
      title={
        flagged
          ? `Needs a look: ${note?.flags.map((f) => FLAG_TEXT[f]).join(', ')}`
          : (note?.thesis ??
            (note
              ? 'Your note'
              : 'Add a note: why you own it, target, stop, review date'))
      }
      className={`rounded-xs p-0.5 transition hover:bg-panelalt ${
        flagged
          ? 'text-amber-600 dark:text-amber-400'
          : note
            ? 'text-accent'
            : 'text-subtle opacity-60 hover:opacity-100'
      }`}
    >
      <NotebookPen size={13} />
    </button>
  )
}
