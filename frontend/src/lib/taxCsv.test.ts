import { describe, expect, it } from 'vitest'
import type { TaxSummary } from '../api'
import { taxSummaryCsv } from './taxCsv'

const summary: TaxSummary = {
  year: 2025,
  as_of: '2025-12-31',
  final: true,
  years: [2026, 2025],
  dividend_tax_pct: 10,
  holdings: [
    {
      ticker: 'BBCA',
      name: 'Bank Central Asia, "Tbk"',
      shares: 1000,
      acquired_year: 2024,
      cost: 1_001_513.4,
      close: 1150,
      market_value: 1_150_000,
    },
  ],
  sales: [],
  dividends: [
    {
      ticker: 'BBCA',
      name: 'Bank Central Asia',
      ex_date: '2025-06-02',
      shares: 1000,
      per_share: 100,
      gross: 100_000,
      tax: 10_000,
      net: 90_000,
    },
  ],
  totals: {
    cost: 1_001_513.4,
    market_value: 1_150_000,
    proceeds: 0,
    sales_tax: 0,
    realized_pl: 0,
    dividends_gross: 100_000,
    dividends_tax: 10_000,
    dividends_net: 90_000,
  },
}

describe('taxSummaryCsv', () => {
  const lines = taxSummaryCsv(summary).split('\r\n')

  it('quotes names and rounds amounts to whole rupiah', () => {
    expect(lines).toContain(
      'BBCA,"Bank Central Asia, ""Tbk""",1000,2024,1001513,1150,1150000',
    )
    expect(lines).toContain('Total,,,,1001513,,1150000')
  })

  it('has the three sections with their totals', () => {
    expect(lines[0]).toBe('Bursa tax summary 2025,as of 2025-12-31')
    expect(lines).toContain(
      '2025-06-02,BBCA,Bank Central Asia,1000,100,100000,10000,90000',
    )
    expect(lines).toContain('Share sales in 2025')
    expect(lines).toContain('Total,,,0,0,,0')
  })
})
