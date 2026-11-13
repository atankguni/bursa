import { useMemo, useState } from 'react'
import {
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Check,
  Loader2,
  Plus,
  RefreshCw,
  ChevronRight,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { DEFAULT_INDEXES, type Stock } from '../api'
import {
  useIndexes,
  useIndices,
  usePortfolio,
  useStatus,
  useStocks,
  useWatchToggle,
} from '../hooks'
import { useSettings } from '../lib/settings'
import {
  fmtChange,
  fmtDateTime,
  fmtMoney,
  fmtMoneySigned,
  fmtPct,
  fmtPrice,
  fmtVolume,
} from '../lib/format'
import BoardBadge from '../components/BoardBadge'
import TickerName from '../components/TickerName'
import IndexMultiSelect from '../components/IndexMultiSelect'
import SignalBadge from '../components/SignalBadge'
import StockDetailModal from '../components/StockDetailModal'
import PageHeader from '../components/ui/PageHeader'
import Stat from '../components/ui/Stat'

type DetailTab = 'chart' | 'fundamentals' | 'recommendation'
type SignalSort = 'off' | 'desc' | 'asc'
const NEXT_SORT: Record<SignalSort, SignalSort> = { off: 'desc', desc: 'asc', asc: 'off' }

export default function Home() {
  const { settings } = useSettings()
  // The user's pick, until the default indexes (Settings) change.
  const defaultsKey = settings.defaultIndexes.join(',')
  const [picked, setPicked] = useState({ defaultsKey, indexes: settings.defaultIndexes })
  const selectedIndexes =
    picked.defaultsKey === defaultsKey ? picked.indexes : settings.defaultIndexes
  const setSelectedIndexes = (indexes: string[]) => setPicked({ defaultsKey, indexes })
  const [selected, setSelected] = useState<Stock | null>(null)
  const [detailTab, setDetailTab] = useState<DetailTab>('chart')
  const [buyOnly, setBuyOnly] = useState(false)
  const [signalSort, setSignalSort] = useState<SignalSort>('off')

  const hidden = settings.hiddenColumns.home
  const rec = (key: string) => !hidden.includes(key)

  const openDetail = (stock: Stock, tab: DetailTab) => {
    setSelected(stock)
    setDetailTab(tab)
  }

  const { data: serverIndexes } = useIndexes()
  const indexOptions =
    serverIndexes && serverIndexes.length > 0 ? serverIndexes : DEFAULT_INDEXES

  const { data: stocks = [], isLoading, isFetching, refetch } = useStocks(selectedIndexes)

  // Real time of the last successful price sync (same source as the footer).
  const { data: status, refetch: refetchStatus } = useStatus()

  const watch = useWatchToggle()

  const summary = useMemo(() => {
    let gainers = 0
    let losers = 0
    let unchanged = 0
    for (const s of stocks) {
      if (s.change_percent == null) unchanged++
      else if (s.change_percent > 0) gainers++
      else if (s.change_percent < 0) losers++
      else unchanged++
    }
    return { gainers, losers, unchanged }
  }, [stocks])

  const signals = useMemo(() => {
    let strongBuy = 0
    let buy = 0
    for (const s of stocks) {
      const r = s.recommendation?.rating
      if (r === 'Strong Buy') strongBuy++
      else if (r === 'Buy') buy++
    }
    return { strongBuy, buy }
  }, [stocks])

  const rows = useMemo(() => {
    let out = stocks
    if (buyOnly) {
      out = out.filter(
        (s) =>
          s.recommendation?.rating === 'Buy' || s.recommendation?.rating === 'Strong Buy',
      )
    }
    if (signalSort !== 'off') {
      out = [...out].sort((a, b) => {
        const sa = a.recommendation?.score ?? -1
        const sb = b.recommendation?.score ?? -1
        return signalSort === 'desc' ? sb - sa : sa - sb
      })
    }
    return out
  }, [stocks, buyOnly, signalSort])

  const colCount = 9 - hidden.length
  const { data: indices } = useIndices()
  const ihsg = indices?.find((i) => i.code === 'COMPOSITE')
  const { data: pf } = usePortfolio()
  const holdingsCount = pf?.holdings.length ?? 0
  const hideValues = settings.hidePortfolioValues
  const toneOf = (v: number | null | undefined) =>
    !settings.colorizeChanges || v == null || v === 0
      ? 'text-muted'
      : v > 0
        ? 'text-bull'
        : 'text-bear'
  const total = summary.gainers + summary.losers + summary.unchanged || 1
  const rated = stocks.filter((x) => x.recommendation).length

  return (
    <main className="page">
      <PageHeader
        title="Today"
        subtitle={
          status?.last_sync
            ? `Prices as of ${fmtDateTime(status.last_sync)}`
            : 'IDX stocks in the indices you follow'
        }
        actions={
          <button
            onClick={() => {
              void refetch()
              void refetchStatus()
            }}
            className="btn btn-ghost"
          >
            <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      {/* Summary band */}
      <section className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        <div className="surface p-4 sm:p-5">
          <Stat
            label="IHSG"
            size="lg"
            value={ihsg?.last != null ? fmtPrice(ihsg.last) : '—'}
            tone="text-ink"
            sub={
              <span className={`font-medium ${toneOf(ihsg?.change_percent)}`}>
                {fmtPct(ihsg?.change_percent) || '—'} today
              </span>
            }
          />
        </div>

        <div className="surface p-4 sm:p-5">
          <div className="eyebrow">Breadth · this view</div>
          <div className="mt-1 text-xl font-semibold tracking-tight tabular-nums">
            <span className="text-bull">{summary.gainers}</span>
            <span className="mx-1.5 text-subtle">/</span>
            <span className="text-bear">{summary.losers}</span>
          </div>
          <div
            className="mt-2 flex h-1.5 overflow-hidden rounded-full bg-panelalt"
            role="img"
            aria-label={`${summary.gainers} up, ${summary.losers} down, ${summary.unchanged} flat`}
          >
            <span
              className="bg-bull"
              style={{ width: `${(summary.gainers / total) * 100}%` }}
            />
            <span
              className="bg-bear"
              style={{ width: `${(summary.losers / total) * 100}%` }}
            />
          </div>
          <div className="mt-1.5 text-2xs text-subtle">
            up / down · {summary.unchanged} flat
          </div>
        </div>

        <div
          className="surface p-4 sm:p-5"
          title="Signals rank each stock against the others; they are not buy/sell advice"
        >
          <Stat
            label="Positive signals"
            size="lg"
            value={signals.strongBuy + signals.buy}
            sub={`${signals.strongBuy} very positive · of ${rated} rated`}
          />
          <button
            onClick={() => setBuyOnly((v) => !v)}
            aria-pressed={buyOnly}
            className={`mt-2 text-2xs font-medium transition-colors ${
              buyOnly ? 'text-accent' : 'text-muted hover:text-ink'
            }`}
          >
            {buyOnly ? '✓ Showing positive only' : 'Show positive only'}
          </button>
        </div>

        {holdingsCount > 0 && pf ? (
          <Link
            to="/portfolio"
            className="surface group p-4 transition-shadow hover:shadow-pop sm:p-5"
          >
            <div className="eyebrow flex items-center justify-between">
              Your portfolio today
              <ChevronRight
                size={14}
                className="text-subtle transition-transform group-hover:translate-x-0.5"
              />
            </div>
            <div
              className={`mt-1 text-xl font-semibold tracking-tight tabular-nums ${toneOf(pf.totals.day_change)}`}
            >
              {hideValues ? '••••••' : fmtMoneySigned(pf.totals.day_change)}
            </div>
            <div className="mt-0.5 text-2xs text-subtle">
              {fmtPct(pf.totals.day_change_pct) || '—'} ·{' '}
              {hideValues ? '••••••' : fmtMoney(pf.totals.market_value)} in{' '}
              {holdingsCount} stock{holdingsCount === 1 ? '' : 's'}
            </div>
          </Link>
        ) : (
          <Link
            to="/portfolio"
            className="surface group flex flex-col justify-between p-4 transition-shadow hover:shadow-pop sm:p-5"
          >
            <div className="eyebrow">Your portfolio</div>
            <div className="mt-1 text-xs text-muted">
              Record your trades to see your day here.
            </div>
            <div className="mt-2 inline-flex items-center gap-1 text-2xs font-medium text-accent">
              Open Portfolio <ChevronRight size={12} />
            </div>
          </Link>
        )}
      </section>

      {/* Toolbar */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted">Indices</span>
          <IndexMultiSelect
            options={indexOptions}
            selected={selectedIndexes}
            onChange={(next) => {
              setSelectedIndexes(next)
              setSelected(null)
            }}
          />
        </div>
        <div className="segmented" role="group" aria-label="Show">
          <button
            onClick={() => setBuyOnly(false)}
            aria-pressed={!buyOnly}
            className="segment"
          >
            All · {stocks.length}
          </button>
          <button
            onClick={() => setBuyOnly(true)}
            aria-pressed={buyOnly}
            className="segment"
          >
            Positive · {signals.strongBuy + signals.buy}
          </button>
        </div>
      </div>

      {watch.error && (
        <p role="alert" className="mb-2 text-xs text-bear">
          {watch.error}
        </p>
      )}
      <div className="surface overflow-hidden">
        <div className="relative overflow-x-auto">
          <table className="w-full whitespace-nowrap text-left text-xs">
            <thead className="table-head">
              <tr>
                <th scope="col" className="px-4 py-3">
                  Ticker
                </th>
                <th scope="col" className="hidden px-4 py-3 md:table-cell">
                  Name
                </th>
                {rec('index') && (
                  <th scope="col" className="hidden px-4 py-3 md:table-cell">
                    Index
                  </th>
                )}
                <th scope="col" className="px-4 py-3 text-right">
                  Last
                </th>
                {rec('change') && (
                  <th scope="col" className="px-4 py-3 text-right">
                    Change
                  </th>
                )}
                {rec('pct') && (
                  <th scope="col" className="px-4 py-3 text-right">
                    %
                  </th>
                )}
                {rec('signal') && (
                  <th scope="col" className="px-4 py-3">
                    <button
                      onClick={() => setSignalSort((s) => NEXT_SORT[s])}
                      className="inline-flex items-center gap-1 hover:text-ink"
                      title="Sort by signal score"
                    >
                      Signal
                      <span className="text-[8px]">
                        {signalSort === 'desc' ? '▼' : signalSort === 'asc' ? '▲' : '↕'}
                      </span>
                    </button>
                  </th>
                )}
                {rec('volume') && (
                  <th scope="col" className="px-4 py-3 text-right">
                    Volume
                  </th>
                )}
                <th scope="col" className="px-4 py-3 text-center">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {isLoading && (
                <tr>
                  <td colSpan={colCount} className="px-4 py-10 text-center text-subtle">
                    Loading market data…
                  </td>
                </tr>
              )}
              {!isLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={colCount} className="px-4 py-10 text-center text-subtle">
                    {buyOnly
                      ? 'No positive signals in this view.'
                      : 'No stocks match the selected indices.'}
                  </td>
                </tr>
              )}
              {rows.map((s) => {
                const up = (s.change ?? 0) >= 0
                const tone = !settings.colorizeChanges
                  ? 'text-muted'
                  : s.change == null
                    ? 'text-muted'
                    : up
                      ? 'text-bull'
                      : 'text-bear'
                const watched = watch.isWatched(s.ticker)
                const watchBusy = watch.isPending(s.ticker)
                return (
                  <tr
                    key={s.ticker}
                    onClick={() => openDetail(s, 'chart')}
                    className="cursor-pointer bg-panel transition-colors hover:bg-panelalt/50"
                  >
                    <td className="px-4 py-3 font-semibold tracking-tight">
                      <span className="inline-flex items-center gap-1.5">
                        {s.ticker}
                        <BoardBadge board={s.board} compact />
                      </span>
                      <TickerName name={s.name} />
                    </td>
                    <td className="hidden px-4 py-3 text-muted md:table-cell">
                      {s.name}
                    </td>
                    {rec('index') && (
                      <td className="hidden px-4 py-3 md:table-cell">
                        <div className="flex flex-wrap gap-1">
                          {s.indices.map((idx) => (
                            <span
                              key={idx}
                              className="rounded-xs bg-panelalt px-1.5 py-0.5 text-2xs font-medium text-muted"
                            >
                              {idx}
                            </span>
                          ))}
                        </div>
                      </td>
                    )}
                    <td className="px-4 py-3 text-right font-semibold tabular-nums">
                      {fmtPrice(s.last_price)}
                    </td>
                    {rec('change') && (
                      <td className={`px-4 py-2 text-right tabular-nums ${tone}`}>
                        <span className="inline-flex items-center justify-end gap-0.5">
                          {s.change != null &&
                            (up ? (
                              <ArrowUpRight size={12} aria-hidden />
                            ) : (
                              <ArrowDownRight size={12} aria-hidden />
                            ))}
                          {fmtChange(s.change)}
                        </span>
                      </td>
                    )}
                    {rec('pct') && (
                      <td className={`px-4 py-2 text-right font-medium ${tone}`}>
                        <span className="inline-flex items-center justify-end gap-0.5 tabular-nums">
                          {s.change != null &&
                            (up ? (
                              <ArrowUpRight size={12} />
                            ) : (
                              <ArrowDownRight size={12} />
                            ))}
                          {fmtPct(s.change_percent)}
                        </span>
                      </td>
                    )}
                    {rec('signal') && (
                      <td className="px-4 py-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            openDetail(s, 'recommendation')
                          }}
                          className="rounded-sm transition hover:opacity-80"
                          title="View signal breakdown"
                        >
                          <SignalBadge rec={s.recommendation} />
                        </button>
                      </td>
                    )}
                    {rec('volume') && (
                      <td className="px-4 py-3 text-right tabular-nums text-subtle">
                        {fmtVolume(s.volume)}
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            openDetail(s, 'fundamentals')
                          }}
                          title="View fundamentals"
                          className="btn btn-ghost btn-icon"
                        >
                          <BarChart3 size={14} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            watch.add(s.ticker)
                          }}
                          disabled={watched && !watchBusy}
                          aria-busy={watchBusy}
                          title={watched ? 'On watchlist' : 'Add to watchlist'}
                          className={`inline-flex items-center justify-center rounded-sm p-2 transition ${
                            watchBusy
                              ? 'cursor-progress text-accent'
                              : watched
                                ? 'cursor-default text-accent'
                                : 'text-muted hover:bg-panelalt hover:text-ink'
                          }`}
                        >
                          {watchBusy ? (
                            <Loader2 size={14} className="animate-spin" aria-hidden />
                          ) : watched ? (
                            <Check size={14} />
                          ) : (
                            <Plus size={14} />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="mt-3 text-2xs text-subtle">
        Signals rank each stock against the others in Bursa; they are not advice.
      </p>

      {selected && (
        <StockDetailModal
          stock={selected}
          onClose={() => setSelected(null)}
          initialTab={detailTab}
        />
      )}
    </main>
  )
}
