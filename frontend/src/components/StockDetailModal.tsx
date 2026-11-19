import { useState } from 'react'
import { ArrowDownRight, ArrowLeftRight, ArrowUpRight, BellPlus } from 'lucide-react'
import { useCompany, useRecommendation } from '../hooks'
import { fmtChange, fmtPct, fmtPrice } from '../lib/format'
import { useSettings } from '../lib/settings'
import AlertModal from './AlertModal'
import BoardBadge from './BoardBadge'
import CompanyPanel from './CompanyPanel'
import Modal from './Modal'
import RecommendationPanel from './RecommendationPanel'
import ChartTab, { useChartOptions } from './stock/ChartTab'
import StockFacts from './stock/StockFacts'
import FundamentalsTab, { type FinTab } from './stock/FundamentalsTab'
import WatchButton from './stock/WatchButton'
import SubTabs from './SubTabs'
import TransactionModal from './TransactionModal'

// The header's small outlined buttons (same look as Watch).
const ACTION =
  'flex items-center gap-1 rounded-sm px-2.5 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink'

// Minimal shape needed to render the modal — both Stock and WatchlistItem fit.
export interface StockLike {
  ticker: string
  name: string
  indices: string[]
  last_price: number | null
  change?: number | null
  change_percent?: number | null
  board?: string | null
}

type Tab = 'chart' | 'fundamentals' | 'recommendation' | 'company'
type CompanyTab = 'overview' | 'board'

const TABS: { value: Tab; label: string }[] = [
  { value: 'chart', label: 'Chart' },
  { value: 'fundamentals', label: 'Fundamentals' },
  { value: 'recommendation', label: 'Signal' },
  { value: 'company', label: 'Company' },
]

export default function StockDetailModal({
  stock,
  onClose,
  initialTab = 'chart',
}: {
  stock: StockLike
  onClose: () => void
  initialTab?: Tab
}) {
  const [tab, setTab] = useState<Tab>(initialTab)
  const [finTab, setFinTab] = useState<FinTab>('financials')
  const [companyTab, setCompanyTab] = useState<CompanyTab>('overview')
  // A form opened on top: record a trade, or add an alert.
  const [sub, setSub] = useState<'trade' | 'alert' | null>(null)
  const { settings } = useSettings()
  // Each tab's choices live here, so they survive switching tabs.
  const chartOptions = useChartOptions()
  const recommendation = useRecommendation(stock.ticker, tab === 'recommendation')
  const company = useCompany(stock.ticker, tab === 'company')

  const up = (stock.change ?? stock.change_percent ?? 0) >= 0
  const tone = !settings.colorizeChanges ? 'text-muted' : up ? 'text-bull' : 'text-bear'

  return (
    <Modal
      label={`${stock.ticker} ${stock.name}`}
      onClose={onClose}
      // Tabs stay put; only the tab content scrolls.
      bodyClassName="flex flex-col"
      header={
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold tracking-tight">{stock.ticker}</h2>
            <BoardBadge board={stock.board} />
            {stock.indices.map((idx) => (
              <span
                key={idx}
                className="rounded-sm bg-panelalt px-2 py-0.5 text-2xs font-medium text-muted"
              >
                {idx}
              </span>
            ))}
          </div>
          <p className="text-xs text-muted">{stock.name}</p>
          <div className="mt-2 flex items-baseline gap-3">
            <span className="text-3xl font-semibold tracking-tight tabular-nums">
              {fmtPrice(stock.last_price)}
            </span>
            {stock.change_percent != null && (
              <span
                className={`flex items-center text-sm font-medium tabular-nums ${tone}`}
              >
                {up ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                {stock.change != null && <>{fmtChange(stock.change)} </>}(
                {fmtPct(stock.change_percent)})
              </span>
            )}
          </div>
          <StockFacts ticker={stock.ticker} price={stock.last_price} />
        </div>
      }
      actions={
        <>
          <button
            onClick={() => setSub('trade')}
            title="Record a buy or sell"
            className={ACTION}
          >
            <ArrowLeftRight size={14} aria-hidden />
            <span className="sr-only sm:not-sr-only">Record trade</span>
          </button>
          <button
            onClick={() => setSub('alert')}
            title="Add a price or dividend alert"
            className={ACTION}
          >
            <BellPlus size={14} aria-hidden />
            <span className="sr-only sm:not-sr-only">Alert</span>
          </button>
          <WatchButton ticker={stock.ticker} />
        </>
      }
    >
      {/* Tabs */}
      <div className="shrink-0">
        <div className="segmented" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.value}
              role="tab"
              aria-selected={tab === t.value}
              onClick={() => setTab(t.value)}
              className="segment"
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Scrollable content region — header + tabs stay pinned */}
      <div
        className={`mt-3 min-h-0 flex-1 overflow-y-auto pr-1 ${tab === 'chart' ? 'flex flex-col' : ''}`}
      >
        {tab === 'chart' && <ChartTab ticker={stock.ticker} options={chartOptions} />}
        {tab === 'fundamentals' && (
          <FundamentalsTab ticker={stock.ticker} finTab={finTab} setFinTab={setFinTab} />
        )}

        {/* Recommendation tab */}
        {tab === 'recommendation' && (
          <div className="mt-3">
            <RecommendationPanel
              data={recommendation.data}
              isLoading={recommendation.isLoading}
              isError={recommendation.isError}
            />
          </div>
        )}

        {/* Company tab */}
        {tab === 'company' && (
          <div className="mt-3 space-y-3">
            <SubTabs<CompanyTab>
              options={[
                { value: 'overview', label: 'Overview' },
                { value: 'board', label: 'Board' },
              ]}
              value={companyTab}
              onChange={setCompanyTab}
            />
            <CompanyPanel
              data={company.data}
              isLoading={company.isLoading}
              isError={company.isError}
              section={companyTab}
            />
          </div>
        )}
      </div>

      {sub === 'trade' && (
        <TransactionModal
          initial={{ ticker: stock.ticker, side: 'buy', price: stock.last_price }}
          onClose={() => setSub(null)}
        />
      )}
      {sub === 'alert' && (
        <AlertModal
          ticker={stock.ticker}
          price={stock.last_price}
          onClose={() => setSub(null)}
        />
      )}
    </Modal>
  )
}
