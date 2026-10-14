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

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl rounded-2xl bg-panel p-6 shadow-2xl ring-1 ring-slate-700"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-semibold">{stock.ticker}</h2>
              {stock.indices.map((idx) => (
                <span
                  key={idx}
                  className="rounded bg-panelalt px-2 py-0.5 text-xs text-slate-300"
                >
                  {idx}
                </span>
              ))}
            </div>
            <p className="text-sm text-slate-400">{stock.name}</p>
            <div className="mt-2 flex items-baseline gap-3">
              <span className="text-2xl font-bold">{fmtPrice(stock.last_price)}</span>
              {stock.change_percent != null && (
                <span className={`flex items-center text-sm font-medium ${tone}`}>
                  {up ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                  {stock.change != null && <>{fmtChange(stock.change)} </>}
                  ({fmtPct(stock.change_percent)})
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 transition hover:bg-panelalt hover:text-white"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <div className="flex overflow-hidden rounded-lg ring-1 ring-slate-700">
            {(['1d', '1m'] as const).map((i) => (
              <button
                key={i}
                onClick={() => setRange(i)}
                className={`px-3 py-1.5 text-sm ${
                  range === i ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                {i === '1d' ? 'Daily' : '1-Min'}
              </button>
            ))}
          </div>
          <div className="flex overflow-hidden rounded-lg ring-1 ring-slate-700">
            <button
              onClick={() => setChartType('candle')}
              className={`flex items-center gap-1 px-3 py-1.5 text-sm ${
                chartType === 'candle' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              <CandlestickChart size={14} /> Candle
            </button>
            <button
              onClick={() => setChartType('line')}
              className={`flex items-center gap-1 px-3 py-1.5 text-sm ${
                chartType === 'line' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              <LineChart size={14} /> Line
            </button>
          </div>
        </div>

        <div className="mt-4">
          {isLoading ? (
            <div className="flex h-[420px] items-center justify-center text-slate-500">
              Loading chart…
            </div>
          ) : data && data.points.length > 0 ? (
            <StockChart data={data.points} chartType={chartType} />
          ) : (
            <div className="flex h-[420px] items-center justify-center text-slate-500">
              No price data yet for this interval.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
