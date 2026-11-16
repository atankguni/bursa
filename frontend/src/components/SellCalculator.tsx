import { useState } from 'react'
import type { Holding } from '../api'
import { useMarketStatus, usePreferences, useStatus } from '../hooks'
import { fmtDay, fmtNum, fmtPrice } from '../lib/format'
import {
  estimateSale,
  floorToStep,
  onPriceStep,
  priceStep,
  sellableLots,
} from '../lib/sellEstimate'
import Modal from './Modal'

const fmtTradeDay = (iso: string) => fmtDay(iso, { weekday: true })

const signed = (v: number) =>
  `${v > 0 ? '+' : v < 0 ? '−' : ''}Rp ${fmtPrice(Math.abs(v))}`

/** What selling (part of) a holding would bring in, after the sell fee and tax. */
export default function SellCalculator({
  holding,
  onClose,
  onRecord,
}: {
  holding: Holding
  onClose: () => void
  /** Open the transaction form with this sale filled in. */
  onRecord: (sale: { lots: number; price: number }) => void
}) {
  const { data: status } = useStatus()
  const { data: market } = useMarketStatus()
  const { tradingCosts } = usePreferences()
  const lotSize = status?.lot_size ?? 100
  const { lots: maxLots, oddShares } = sellableLots(holding.quantity, lotSize)
  const [lots, setLots] = useState(String(maxLots))
  const [price, setPrice] = useState(
    holding.price ? String(floorToStep(holding.price)) : '',
  )

  const lotsN = Math.floor(Number(lots))
  const priceN = Number(price)
  const lotsOk = lotsN >= 1 && lotsN <= maxLots
  const priceOk = onPriceStep(priceN)
  const sale =
    lotsOk && priceOk
      ? estimateSale({
          shares: lotsN * lotSize,
          price: priceN,
          avgCost: holding.avg_cost,
          sellFeePct: tradingCosts.sell_fee_pct,
        })
      : null

  const inputCls = 'input tabular-nums'

  return (
    <Modal
      size="form"
      title={`Sell ${holding.ticker}`}
      onClose={onClose}
      footer={
        <>
          <span />
          <div className="flex gap-2">
            <button onClick={onClose} className="btn btn-secondary">
              Close
            </button>
            <button
              onClick={() => sale && onRecord({ lots: lotsN, price: priceN })}
              disabled={!sale}
              title="After you sold at your broker: record it in the portfolio"
              className="btn btn-primary"
            >
              Record this sale
            </button>
          </div>
        </>
      }
    >
      <div className="space-y-4">
        {maxLots === 0 ? (
          <p className="text-xs text-muted">
            You hold {fmtNum(holding.quantity)} shares, less than one lot ({lotSize}{' '}
            shares). Odd lots sell in IDX&apos;s odd-lot market, usually at a different
            price.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 flex justify-between text-xs text-muted">
                  Lots
                  <button
                    type="button"
                    onClick={() => setLots(String(maxLots))}
                    className="text-accent hover:underline"
                  >
                    All ({maxLots})
                  </button>
                </label>
                <input
                  type="number"
                  min={1}
                  max={maxLots}
                  step={1}
                  value={lots}
                  onChange={(e) => setLots(e.target.value)}
                  className={inputCls}
                />
                <p className="mt-1 text-2xs text-subtle">
                  {lotsOk
                    ? `= ${fmtNum(lotsN * lotSize)} shares`
                    : `1 to ${maxLots} lots`}
                </p>
              </div>
              <div>
                <label className="mb-1 flex justify-between text-xs text-muted">
                  Price
                  {holding.price != null && (
                    <button
                      type="button"
                      onClick={() => setPrice(String(floorToStep(holding.price ?? 0)))}
                      className="text-accent hover:underline"
                    >
                      Last {fmtPrice(holding.price)}
                    </button>
                  )}
                </label>
                <input
                  type="number"
                  min={1}
                  step={priceN > 0 ? priceStep(priceN) : 1}
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className={inputCls}
                />
                <p className="mt-1 text-2xs text-subtle">
                  {priceN > 0 && !priceOk
                    ? `IDX prices move in steps of Rp ${priceStep(priceN)} here (e.g. ${fmtPrice(floorToStep(priceN))})`
                    : 'Your limit price, or the last price'}
                </p>
              </div>
            </div>

            {sale && (
              <dl className="space-y-1.5 rounded-md bg-panelalt/50 p-3 text-xs ring-1 ring-line">
                <Line label="Sale value" value={`Rp ${fmtPrice(sale.gross)}`} />
                <Line
                  label={`Fee + tax (${tradingCosts.sell_fee_pct}%)`}
                  hint="Broker fee and levies, incl. the 0.1% sales tax"
                  value={`−Rp ${fmtPrice(sale.costs)}`}
                />
                <div className="border-t border-line pt-1.5">
                  <Line
                    label="Cash you receive"
                    value={`Rp ${fmtPrice(sale.net)}`}
                    strong
                  />
                </div>
                {market?.settlement_date && (
                  <Line
                    label="Arrives on"
                    hint={`Sold on ${fmtTradeDay(market.trade_date ?? market.settlement_date)}; IDX settles two trading days later (T+2)`}
                    value={fmtTradeDay(market.settlement_date)}
                  />
                )}
                <div className="border-t border-line pt-1.5">
                  <Line
                    label="Cost of these shares"
                    hint={`Average Rp ${fmtPrice(holding.avg_cost)} per share, buy fees included`}
                    value={`Rp ${fmtPrice(sale.costBasis)}`}
                  />
                  <Line
                    label="Profit / loss"
                    value={`${signed(sale.pl)}${
                      sale.plPct != null
                        ? ` (${sale.plPct > 0 ? '+' : ''}${fmtNum(sale.plPct, 2)}%)`
                        : ''
                    }`}
                    tone={sale.pl > 0 ? 'text-bull' : sale.pl < 0 ? 'text-bear' : ''}
                  />
                </div>
              </dl>
            )}
          </>
        )}

        <p className="text-2xs text-subtle">
          An estimate from your fee rates: the price you actually get can differ, and some
          brokers round fees or charge a minimum. Check it against your broker&apos;s
          confirmation.
          {oddShares > 0 &&
            maxLots > 0 &&
            ` Your ${oddShares} odd-lot shares (under one lot) sell separately in the odd-lot market.`}
        </p>
      </div>
    </Modal>
  )
}

export function Line({
  label,
  value,
  hint,
  strong = false,
  tone = '',
}: {
  label: string
  value: string
  hint?: string
  strong?: boolean
  tone?: string
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className={strong ? 'font-semibold text-ink' : 'text-muted'}>
        {label}
        {hint && <div className="text-2xs font-normal text-subtle">{hint}</div>}
      </dt>
      <dd
        className={`text-right whitespace-nowrap tabular-nums ${strong ? 'text-sm font-semibold text-ink' : 'text-ink'} ${tone}`}
      >
        {value}
      </dd>
    </div>
  )
}
