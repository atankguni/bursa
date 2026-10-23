/** The stock modal's fundamentals tab: financials, valuation and dividends. */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchFundamentals } from '../../api'
import { queryKeys, useDividends, useFundamentals, useValuation } from '../../hooks'
import { fmtPercent, fmtPrice, fmtRatio } from '../../lib/format'
import FundamentalsPanel from '../FundamentalsPanel'
import SubTabs from '../SubTabs'

export type FinTab = 'financials' | 'valuation' | 'dividends'

export default function FundamentalsTab({
  ticker,
  finTab,
  setFinTab,
}: {
  ticker: string
  finTab: FinTab
  setFinTab: (tab: FinTab) => void
}) {
  const queryClient = useQueryClient()
  const fundamentals = useFundamentals(ticker, finTab === 'financials')
  const refreshFundamentals = useMutation({
    mutationFn: () => fetchFundamentals(ticker, true),
    onSuccess: (data) => queryClient.setQueryData(queryKeys.fundamentals(ticker), data),
  })
  return (
    <div className="mt-3 space-y-3">
      <SubTabs<FinTab>
        options={[
          { value: 'financials', label: 'Financials' },
          { value: 'valuation', label: 'Valuation' },
          { value: 'dividends', label: 'Dividends' },
        ]}
        value={finTab}
        onChange={setFinTab}
      />

      {finTab === 'financials' && (
        <FundamentalsPanel
          data={fundamentals.data}
          isLoading={fundamentals.isLoading}
          isError={fundamentals.isError}
          onRefresh={() => refreshFundamentals.mutate()}
          isRefreshing={refreshFundamentals.isPending}
        />
      )}

      {finTab === 'valuation' && <ValuationCard ticker={ticker} />}
      {finTab === 'dividends' && <DividendsCard ticker={ticker} />}
    </div>
  )
}

function ValuationCard({ ticker }: { ticker: string }) {
  const valuation = useValuation(ticker, true)
  return valuation.data && (valuation.data.pbv != null || valuation.data.roe != null) ? (
    <div className="surface p-4">
      <div className="mb-3 text-[10px] uppercase tracking-wider text-muted">
        Relative valuation
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          {
            label: 'PBV',
            value: valuation.data.pbv,
            range: `${valuation.data.pbv_min ?? '—'} – ${valuation.data.pbv_max ?? '—'}`,
            pct: valuation.data.pbv_percentile,
            window: `${valuation.data.window_days}d`,
          },
          {
            label: 'RoE',
            value: valuation.data.roe,
            range: `${valuation.data.years.length} yrs`,
            pct: valuation.data.roe_percentile,
            window: 'history',
          },
        ].map((row) => (
          <div key={row.label} className="text-xs">
            <div className="flex items-baseline justify-between">
              <span className="text-muted">
                {row.label}{' '}
                <span className="font-medium text-ink">
                  {row.label === 'PBV' ? fmtRatio(row.value) : fmtPercent(row.value)}
                </span>
              </span>
              <span className="text-[10px] text-subtle">{row.range}</span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-xs bg-panelalt">
              <div
                className="h-full rounded-xs bg-accent"
                style={{ width: `${row.pct ?? 0}%` }}
              />
            </div>
            <div className="mt-1 text-[10px] text-subtle">
              {row.pct != null ? `${row.pct.toFixed(0)}th percentile` : '—'} · vs{' '}
              {row.window}
            </div>
          </div>
        ))}
      </div>
    </div>
  ) : (
    <div className="py-10 text-center text-sm text-muted">
      {valuation.isLoading ? 'Loading valuation…' : 'No valuation data available.'}
    </div>
  )
}

function DividendsCard({ ticker }: { ticker: string }) {
  const dividends = useDividends(ticker, true)
  return dividends.data && dividends.data.history.length > 0 ? (
    <div className="surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider text-muted">Dividends</span>
        <span className="text-xs text-muted">
          Trailing DPS{' '}
          <span className="font-medium text-ink">
            {fmtPrice(dividends.data.trailing_dps)}
          </span>
          {dividends.data.yield_percent != null && (
            <>
              {' · yield '}
              <span className="font-medium text-bull">
                {dividends.data.yield_percent.toFixed(2)}%
              </span>
            </>
          )}
        </span>
      </div>
      <ul className="divide-y divide-line text-xs">
        {dividends.data.history.slice(0, 8).map((d) => (
          <li key={d.ex_date} className="flex justify-between py-1.5">
            <span className="text-muted">{d.ex_date}</span>
            <span className="tabular-nums text-ink">{fmtPrice(d.amount)}</span>
          </li>
        ))}
      </ul>
    </div>
  ) : (
    <div className="py-10 text-center text-sm text-muted">
      {dividends.isLoading ? 'Loading dividends…' : 'No dividend history available.'}
    </div>
  )
}
