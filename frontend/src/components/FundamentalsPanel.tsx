import { AlertCircle, RefreshCw } from 'lucide-react'
import type { Fundamental, FundamentalsResponse } from '../api'
import { fmtCompact, fmtPercent, fmtRatio } from '../lib/format'

interface Props {
  data?: FundamentalsResponse
  isLoading: boolean
  isError?: boolean
  onRefresh?: () => void
  isRefreshing?: boolean
}

/** RoE for a single fiscal year (net income / equity); currency cancels out. */
const roeOf = (f: Fundamental) =>
  f.net_income != null && f.equity ? f.net_income / f.equity : null

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-panelalt px-3 py-2 ring-1 ring-line">
      <div className="text-[10px] uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-0.5 text-sm font-semibold text-ink">{value}</div>
    </div>
  )
}

export default function FundamentalsPanel({
  data,
  isLoading,
  isError,
  onRefresh,
  isRefreshing,
}: Props) {
  if (isLoading) {
    return (
      <div className="flex h-[400px] items-center justify-center gap-2 text-muted">
        <RefreshCw size={16} className="animate-spin" /> Fetching financials…
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-2 text-bear">
        <AlertCircle size={20} />
        <span className="text-sm">Could not load financials.</span>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="mt-1 rounded-lg px-2.5 py-1 text-xs text-muted ring-1 ring-line transition hover:bg-panelalt hover:text-ink"
          >
            Retry
          </button>
        )}
      </div>
    )
  }

  const latest = data?.latest
  const metrics = data?.metrics
  if (!latest || !metrics) {
    return (
      <div className="flex h-[400px] items-center justify-center text-muted">
        No financial data available for this ticker.
      </div>
    )
  }

  const years = [...(data?.yearly ?? [])].sort((a, b) => a.fiscal_year - b.fiscal_year)
  const currency = latest.financial_currency
  const showCurrency = currency && currency !== 'IDR'

  return (
    <div className="space-y-4">
      {/* Header: year + currency + refresh */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs text-muted">
          <span>
            Latest fiscal year: <span className="text-ink">{latest.fiscal_year}</span>
          </span>
          {showCurrency && (
            <span
              title={`Reported in ${currency}, converted to IDR`}
              className="rounded bg-panelalt px-1.5 py-0.5 text-[10px]"
            >
              {currency} → IDR
            </span>
          )}
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-muted ring-1 ring-line transition hover:bg-panelalt hover:text-ink disabled:opacity-50"
          >
            <RefreshCw size={12} className={isRefreshing ? 'animate-spin' : ''} />
            Re-fetch
          </button>
        )}
      </div>

      {/* Key metric cards */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="Market Cap" value={fmtCompact(metrics.market_cap)} />
        <Metric label="PBV" value={fmtRatio(metrics.pbv)} />
        <Metric label="RoE" value={fmtPercent(metrics.roe)} />
        <Metric label="Shares" value={fmtCompact(latest.total_shares)} />
      </div>

      {/* Latest-year breakdown */}
      <div className="overflow-x-auto rounded-lg ring-1 ring-line">
        <table className="w-full whitespace-nowrap text-left text-xs">
          <thead className="bg-panelalt text-[10px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2">Metric</th>
              <th className="px-3 py-2 text-right">{latest.fiscal_year}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {[
              ['Revenue', fmtCompact(latest.revenue)],
              ['Net Income', fmtCompact(latest.net_income)],
              ['Total Assets', fmtCompact(latest.total_assets)],
              ['Total Liabilities', fmtCompact(latest.total_liabilities)],
              ['Equity', fmtCompact(latest.equity)],
              ['Book Value', fmtCompact(metrics.book_value)],
              ['Market Cap', fmtCompact(metrics.market_cap)],
              ['PBV', fmtRatio(metrics.pbv)],
              ['RoE', fmtPercent(metrics.roe)],
            ].map(([label, value]) => (
              <tr key={label} className="bg-panel">
                <td className="px-3 py-1.5 text-muted">{label}</td>
                <td className="px-3 py-1.5 text-right font-medium text-ink">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Multi-year trend */}
      {years.length > 1 && (
        <div className="overflow-x-auto rounded-lg ring-1 ring-line">
          <table className="w-full whitespace-nowrap text-left text-xs">
            <thead className="bg-panelalt text-[10px] uppercase tracking-wide text-muted">
              <tr>
                <th className="px-3 py-2">Year</th>
                <th className="px-3 py-2 text-right">Revenue</th>
                <th className="px-3 py-2 text-right">Net Income</th>
                <th className="px-3 py-2 text-right">Equity</th>
                <th className="px-3 py-2 text-right">RoE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {years.map((y) => (
                <tr key={y.fiscal_year} className="bg-panel">
                  <td className="px-3 py-1.5 font-medium text-ink">{y.fiscal_year}</td>
                  <td className="px-3 py-1.5 text-right text-subtle">
                    {fmtCompact(y.revenue)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-subtle">
                    {fmtCompact(y.net_income)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-subtle">
                    {fmtCompact(y.equity)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-muted">
                    {fmtPercent(roeOf(y))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[11px] text-subtle">
        Figures normalized to IDR (foreign filers converted) · PBV = market cap ÷ book
        value · RoE = net income ÷ equity.
      </p>
    </div>
  )
}
