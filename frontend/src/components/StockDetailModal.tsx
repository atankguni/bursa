import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowDownRight,
  ArrowUpRight,
  CandlestickChart,
  LineChart,
  X,
} from 'lucide-react'
import { fetchHistory } from '../api'
import { fmtChange, fmtPct, fmtPrice } from '../lib/format'
import StockChart from './StockChart'

// Minimal shape needed to render the modal — both Stock and WatchlistItem fit.
export interface StockLike {
  ticker: string
  name: string
  indices: string[]
  last_price: number | null
  change?: number | null
  change_percent?: number | null
}

export default function StockDetailModal({
  stock,
  onClose,
}: {
  stock: StockLike
  onClose: () => void
}) {
  const [range, setRange] = useState<'1d' | '1m'>('1d')
  const [chartType, setChartType] = useState<'candle' | 'line'>('candle')

  const { data, isLoading } = useQuery({
    queryKey: ['history', stock.ticker, range],
    queryFn: () => fetchHistory(stock.ticker, range),
  })

  const up = (stock.change ?? stock.change_percent ?? 0) >= 0
  const tone = up ? 'text-bull' : 'text-bear'
  const seg = (active: boolean) =>
    `px-2.5 py-1 text-xs transition ${
      active ? 'bg-active text-ink' : 'text-muted hover:text-ink'
    }`

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl rounded-xl bg-panel p-5 shadow-2xl ring-1 ring-line"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold">{stock.ticker}</h2>
              {stock.indices.map((idx) => (
                <span
                  key={idx}
                  className="rounded bg-panelalt px-1.5 py-0.5 text-[10px] text-muted"
                >
                  {idx}
                </span>
              ))}
            </div>
            <p className="text-xs text-muted">{stock.name}</p>
            <div className="mt-1.5 flex items-baseline gap-3">
              <span className="text-xl font-bold">{fmtPrice(stock.last_price)}</span>
              {stock.change_percent != null && (
                <span className={`flex items-center text-xs font-medium ${tone}`}>
                  {up ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                  {stock.change != null && <>{fmtChange(stock.change)} </>}
                  ({fmtPct(stock.change_percent)})
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted transition hover:bg-panelalt hover:text-ink"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <div className="flex overflow-hidden rounded-lg ring-1 ring-line">
            {(['1d', '1m'] as const).map((i) => (
              <button key={i} onClick={() => setRange(i)} className={seg(range === i)}>
                {i === '1d' ? 'Daily' : '1-Min'}
              </button>
            ))}
          </div>
          <div className="flex overflow-hidden rounded-lg ring-1 ring-line">
            <button
              onClick={() => setChartType('candle')}
              className={`flex items-center gap-1 ${seg(chartType === 'candle')}`}
            >
              <CandlestickChart size={13} /> Candle
            </button>
            <button
              onClick={() => setChartType('line')}
              className={`flex items-center gap-1 ${seg(chartType === 'line')}`}
            >
              <LineChart size={13} /> Line
            </button>
          </div>
        </div>

        <div className="mt-3">
          {isLoading ? (
            <div className="flex h-[400px] items-center justify-center text-muted">
              Loading chart…
            </div>
          ) : data && data.points.length > 0 ? (
            <StockChart data={data.points} chartType={chartType} />
          ) : (
            <div className="flex h-[400px] items-center justify-center text-muted">
              No price data yet for this interval.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
