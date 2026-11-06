/**
 * What selling shares would bring in: sale value minus the sell fee (broker fee
 * + levies + the 0.1% sales tax, as one rate from Settings → Trading costs), and
 * the profit against their average cost (which includes buy fees).
 */

/** IDX price step (fraksi harga) for a price: orders must be a multiple of it. */
export function priceStep(price: number): number {
  if (price < 200) return 1
  if (price < 500) return 2
  if (price < 2000) return 5
  if (price < 5000) return 10
  return 25
}

/** Whether `price` is a valid IDX order price (a positive multiple of its step). */
export function onPriceStep(price: number): boolean {
  return price > 0 && Number.isInteger(price / priceStep(price))
}

/** The nearest valid IDX order price at or below `price`. */
export function floorToStep(price: number): number {
  return Math.floor(price / priceStep(price)) * priceStep(price)
}

export interface SaleEstimate {
  shares: number
  gross: number // shares × price
  costs: number // sell fee + tax, rounded to whole rupiah like the transaction form
  net: number // what reaches the account
  costBasis: number // what those shares cost (average cost, buy fees included)
  pl: number // net − cost basis
  plPct: number | null // of the cost basis
}

export function estimateSale({
  shares,
  price,
  avgCost,
  sellFeePct,
}: {
  shares: number
  price: number
  avgCost: number
  sellFeePct: number
}): SaleEstimate {
  const gross = shares * price
  const costs = Math.round((gross * sellFeePct) / 100)
  const net = gross - costs
  const costBasis = shares * avgCost
  const pl = net - costBasis
  return {
    shares,
    gross,
    costs,
    net,
    costBasis,
    pl,
    plPct: costBasis > 0 ? (pl / costBasis) * 100 : null,
  }
}

/** Whole lots that can be sold in the regular market, and the leftover odd-lot shares. */
export function sellableLots(
  shares: number,
  lotSize: number,
): { lots: number; oddShares: number } {
  const lots = Math.floor(shares / lotSize)
  return { lots, oddShares: shares - lots * lotSize }
}
