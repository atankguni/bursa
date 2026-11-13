import type { TaxSummary } from '../api'

/**
 * The tax summary as one CSV file (three sections), for a spreadsheet or the
 * person who files the return. Amounts in whole rupiah without separators, so
 * any locale's spreadsheet reads them as numbers.
 */

const cell = (v: string | number | null | undefined) => {
  if (v == null) return ''
  if (typeof v === 'number') return String(v)
  return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v
}

const rp = (v: number | null | undefined) => (v == null ? null : Math.round(v))

export function taxSummaryCsv(s: TaxSummary): string {
  const rows: (string | number | null)[][] = []
  rows.push([
    `Bursa tax summary ${s.year}`,
    s.final ? `as of ${s.as_of}` : `provisional, as of ${s.as_of}`,
  ])
  rows.push([])

  rows.push([`Shares held on ${s.as_of}`])
  rows.push([
    'Ticker',
    'Name',
    'Shares',
    'Year acquired',
    'Acquisition cost (IDR)',
    'Close (IDR)',
    'Market value (IDR)',
  ])
  for (const h of s.holdings) {
    rows.push([
      h.ticker,
      h.name,
      h.shares,
      h.acquired_year,
      rp(h.cost),
      h.close,
      rp(h.market_value),
    ])
  }
  rows.push(['Total', '', '', '', rp(s.totals.cost), '', rp(s.totals.market_value)])
  rows.push([])

  rows.push([`Cash dividends in ${s.year} (by ex-date)`])
  rows.push([
    'Ex-date',
    'Ticker',
    'Name',
    'Shares',
    'Per share (IDR)',
    'Gross (IDR)',
    `Tax ${s.dividend_tax_pct}% (IDR)`,
    'Net (IDR)',
  ])
  for (const d of s.dividends) {
    rows.push([
      d.ex_date,
      d.ticker,
      d.name,
      d.shares,
      d.per_share,
      rp(d.gross),
      rp(d.tax),
      rp(d.net),
    ])
  }
  rows.push([
    'Total',
    '',
    '',
    '',
    '',
    rp(s.totals.dividends_gross),
    rp(s.totals.dividends_tax),
    rp(s.totals.dividends_net),
  ])
  rows.push([])

  rows.push([`Share sales in ${s.year}`])
  rows.push([
    'Ticker',
    'Name',
    'Shares',
    'Sale value (IDR)',
    'Final tax 0.1% (IDR)',
    'Fees incl. that tax (IDR)',
    'Realized P/L (IDR)',
  ])
  for (const x of s.sales) {
    rows.push([
      x.ticker,
      x.name,
      x.shares,
      rp(x.proceeds),
      rp(x.sales_tax),
      rp(x.fees),
      rp(x.realized_pl),
    ])
  }
  rows.push([
    'Total',
    '',
    '',
    rp(s.totals.proceeds),
    rp(s.totals.sales_tax),
    '',
    rp(s.totals.realized_pl),
  ])

  return rows.map((r) => r.map(cell).join(',')).join('\r\n') + '\r\n'
}

/** Save the summary as `bursa-tax-<year>.csv`. */
export function downloadTaxCsv(s: TaxSummary) {
  // A BOM so Excel opens the file as UTF-8.
  const blob = new Blob(['﻿', taxSummaryCsv(s)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `bursa-tax-${s.year}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
