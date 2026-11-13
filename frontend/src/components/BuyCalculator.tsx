import { useState } from 'react'
import type { Holding } from '../api'
import { useCash, usePreferences, useStatus } from '../hooks'
import { affordableLots, estimateBuy } from '../lib/buyEstimate'
import { fmtPrice } from '../lib/format'
import { floorToStep, onPriceStep, priceStep } from '../lib/sellEstimate'
import Modal from './Modal'
import { Line } from './SellCalculator'

const pct = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)}%`

/** What buying more of a holding does to its average cost and break-even price. */
export default function BuyCalculator({
  holding,
  onClose,
  onRecord,
}: {
  holding: Holding
  onClose: () => void
  /** Open the transaction form with this buy filled in. */
  onRecord: (buy: { lots: number; price: number }) => void
}) {
  const { data: status } = useStatus()
  const { data: cash } = useCash()
  const { tradingCosts } = usePreferences()
  const lotSize = status?.lot_size ?? 100
  const [lots, setLots] = useState('1')
  const [price, setPrice] = useState(
    holding.price ? String(floorToStep(holding.price)) : '',
  )

  const lotsN = Math.floor(Number(lots))
  const priceN = Number(price)
  const priceOk = onPriceStep(priceN)
  const buy =
    lotsN >= 1 && priceOk
      ? estimateBuy({
          heldShares: holding.quantity,
          avgCost: holding.avg_cost,
          buyShares: lotsN * lotSize,
          price: priceN,
          buyFeePct: tradingCosts.buy_fee_pct,
          sellFeePct: tradingCosts.sell_fee_pct,
        })
      : null
  // Cash only means something once deposits are recorded (Cash panel).
  const available = cash?.tracked ? cash.available : null
  const maxLots =
    available != null && priceOk
      ? affordableLots(available, priceN, lotSize, tradingCosts.buy_fee_pct)
      : null

  const inputCls =
    'w-full rounded-sm bg-panelalt px-3 py-2 text-sm tabular-nums text-ink ring-1 ring-line-strong outline-hidden focus:ring-accent'

  return (
    <Modal
      size="form"
      title={`Buy more ${holding.ticker}`}
      onClose={onClose}
      footer={
        <>
          <span />
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-sm px-3 py-1.5 text-xs text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
            >
              Close
            </button>
            <button
              onClick={() => buy && onRecord({ lots: lotsN, price: priceN })}
              disabled={!buy}
              title="After you bought at your broker: record it in the portfolio"
              className="rounded-sm bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink transition hover:opacity-90 disabled:opacity-50"
            >
              Record this buy
            </button>
          </div>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="buy-lots"
              className="mb-1 flex justify-between text-xs text-muted"
            >
              Lots
              {maxLots != null && maxLots > 0 && (
                <button
                  type="button"
                  onClick={() => setLots(String(maxLots))}
                  className="text-accent hover:underline"
                  title="As many as your available cash buys, fee included"
                >
                  Max ({maxLots})
                </button>
              )}
            </label>
            <input
              id="buy-lots"
              type="number"
              min={1}
              step={1}
              value={lots}
              onChange={(e) => setLots(e.target.value)}
              className={inputCls}
            />
            <p className="mt-1 text-[10px] text-subtle">
              {lotsN >= 1
                ? `= ${(lotsN * lotSize).toLocaleString('en-US')} shares`
                : '1 lot or more'}
            </p>
          </div>
          <div>
            <label
              htmlFor="buy-price"
              className="mb-1 flex justify-between text-xs text-muted"
            >
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
              id="buy-price"
              type="number"
              min={1}
              step={priceN > 0 ? priceStep(priceN) : 1}
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className={inputCls}
            />
            <p className="mt-1 text-[10px] text-subtle">
              {priceN > 0 && !priceOk
                ? `IDX prices move in steps of Rp ${priceStep(priceN)} here (e.g. ${fmtPrice(floorToStep(priceN))})`
                : 'Your limit price, or the last price'}
            </p>
          </div>
        </div>

        {buy && (
          <dl className="space-y-1.5 rounded-md bg-panelalt/50 p-3 text-xs ring-1 ring-line">
            <Line label="Buy value" value={`Rp ${fmtPrice(buy.gross)}`} />
            <Line
              label={`Fee (${tradingCosts.buy_fee_pct}%)`}
              value={`Rp ${fmtPrice(buy.fee)}`}
            />
            <div className="border-t border-line pt-1.5">
              <Line label="Cash needed" value={`Rp ${fmtPrice(buy.total)}`} strong />
              {available != null && (
                <Line
                  label="Cash left after"
                  hint="From the Cash panel"
                  value={`Rp ${fmtPrice(available - buy.total)}`}
                  tone={available - buy.total < 0 ? 'text-bear' : ''}
                />
              )}
            </div>
            <div className="border-t border-line pt-1.5">
              <Line
                label="Average cost"
                hint="Per share, fees included"
                value={`Rp ${fmtPrice(holding.avg_cost)} → ${fmtPrice(buy.avgCost)}${
                  buy.avgChangePct != null ? ` (${pct(buy.avgChangePct)})` : ''
                }`}
              />
              <Line
                label="Break-even price"
                hint="Lowest price where selling it all gets your money back, after the sell fee and tax"
                value={`${buy.breakEvenBefore != null ? `${fmtPrice(buy.breakEvenBefore)} → ` : ''}${
                  buy.breakEven != null ? fmtPrice(buy.breakEven) : '—'
                }`}
                strong
              />
              {holding.price != null && buy.breakEven != null && (
                <Line
                  label="Needed from the last price"
                  value={pct((buy.breakEven / holding.price - 1) * 100)}
                />
              )}
              <Line
                label="Holding after"
                value={`${(buy.shares / lotSize).toLocaleString('en-US')} lots`}
              />
            </div>
          </dl>
        )}

        <p className="text-[11px] text-subtle">
          Averaging down lowers the price you need, but puts more money in the same stock:
          check that your reason for owning it still holds. An estimate from your fee
          rates (Settings → Trading costs).
        </p>
      </div>
    </Modal>
  )
}
