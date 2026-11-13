/**
 * What buying more of a holding (or a first position) does: the cost with the
 * buy fee, the new average cost, and the break-even price, the lowest valid IDX
 * price at which selling everything gets the money back after the sell fee + tax.
 * Fee percentages come from Settings → Trading costs.
 */
import { priceStep } from './sellEstimate'

/** The nearest valid IDX order price at or above `price`. */
export function ceilToStep(price: number): number {
  return Math.ceil(price / priceStep(price)) * priceStep(price)
}

/** Lowest valid price that returns `avgCost` per share after the sell fee. */
export function breakEven(avgCost: number, sellFeePct: number): number | null {
  if (!(avgCost > 0) || sellFeePct >= 100) return null
  return ceilToStep(avgCost / (1 - sellFeePct / 100))
}

/** Whole lots `budget` buys at `price`, fee included. */
export function affordableLots(
  budget: number,
  price: number,
  lotSize: number,
  buyFeePct: number,
): number {
  if (!(budget > 0) || !(price > 0)) return 0
  let lots = Math.floor(budget / (price * lotSize * (1 + buyFeePct / 100)))
  // The fee is rounded like the transaction form: step back if that tips it over.
  while (lots > 0 && buyCost(lots * lotSize, price, buyFeePct).total > budget) lots--
  return lots
}

function buyCost(shares: number, price: number, buyFeePct: number) {
  const gross = shares * price
  const fee = Math.round((gross * buyFeePct) / 100)
  return { gross, fee, total: gross + fee }
}

export interface BuyEstimate {
  gross: number
  fee: number
  total: number // what leaves the account
  shares: number // after the buy
  avgCost: number // after the buy, fees included
  avgChangePct: number | null // vs the current average
  breakEven: number | null // after the buy
  breakEvenBefore: number | null
}

export function estimateBuy({
  heldShares,
  avgCost,
  buyShares,
  price,
  buyFeePct,
  sellFeePct,
}: {
  heldShares: number
  avgCost: number
  buyShares: number
  price: number
  buyFeePct: number
  sellFeePct: number
}): BuyEstimate {
  const { gross, fee, total } = buyCost(buyShares, price, buyFeePct)
  const shares = heldShares + buyShares
  const newAvg = shares > 0 ? (heldShares * avgCost + total) / shares : 0
  return {
    gross,
    fee,
    total,
    shares,
    avgCost: newAvg,
    avgChangePct: heldShares > 0 && avgCost > 0 ? (newAvg / avgCost - 1) * 100 : null,
    breakEven: breakEven(newAvg, sellFeePct),
    breakEvenBefore: heldShares > 0 ? breakEven(avgCost, sellFeePct) : null,
  }
}
