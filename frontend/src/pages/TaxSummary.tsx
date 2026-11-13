import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Download, Printer } from 'lucide-react'
import { errorMessage } from '../api'
import { useStatus, useTaxSummary } from '../hooks'
import { useSettings } from '../lib/settings'
import { fmtPrice } from '../lib/format'
import { downloadTaxCsv } from '../lib/taxCsv'
import TickerName from '../components/TickerName'

/** Until the return is due (31 March), last year is the one being filed. */
function defaultYear(now = new Date()) {
  return now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear()
}

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

const th = 'px-3 py-2 font-medium'
const td = 'px-3 py-1.5 tabular-nums'

/** A year's holdings on 31 December, dividends and sales, for the SPT Tahunan. */
export default function TaxSummary() {
  const [year, setYear] = useState(defaultYear)
  const { data: s, isLoading, error } = useTaxSummary(year)
  const { data: status } = useStatus()
  const lotSize = status?.lot_size ?? 100
  const { settings, update } = useSettings()
  const hide = settings.hidePortfolioValues
  // Amounts in whole rupiah, masked (not rendered) while values are hidden.
  const rp = (v: number | null | undefined) =>
    hide ? '••••••' : v == null ? '—' : fmtPrice(Math.round(v))
  const years = s?.years ?? [year]

  const btn = 'btn btn-secondary disabled:opacity-50'

  return (
    <main className="page max-w-5xl">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3 lg:mb-6">
        <div>
          <Link
            to="/portfolio"
            className="mb-1 inline-flex items-center gap-1 text-2xs text-muted hover:text-ink print:hidden"
          >
            <ArrowLeft size={12} /> Portfolio
          </Link>
          <h2 className="page-title">Tax summary {year}</h2>
          <p className="page-sub">
            For the annual tax return (SPT Tahunan), from the transactions you recorded
          </p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <label className="text-xs text-muted">
            Year{' '}
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="input input-sm ml-1 w-auto"
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>
          {hide && (
            <button
              onClick={() => update({ hidePortfolioValues: false })}
              className={btn}
            >
              Show values
            </button>
          )}
          <button onClick={() => window.print()} disabled={!s || hide} className={btn}>
            <Printer size={14} /> Print
          </button>
          <button onClick={() => s && downloadTaxCsv(s)} disabled={!s} className={btn}>
            <Download size={14} /> CSV
          </button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-subtle">Loading…</p>}
      {error && (
        <p role="alert" className="text-sm text-bear">
          {errorMessage(error, "Couldn't load the tax summary.")}
        </p>
      )}

      {s && (
        <div className="space-y-6">
          {!s.final && (
            <p className="rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-700 ring-1 ring-amber-500/20 dark:text-amber-400">
              {s.year} isn&apos;t over: these are the figures as of {fmtDay(s.as_of)}. The
              return uses 31 December, so check again after the year ends.
            </p>
          )}

          <Section
            title={`Shares held on ${fmtDay(s.as_of)}`}
            hint="SPT: Harta (Lampiran 1 Bagian A). Report each stock at its acquisition cost (harga perolehan) with the year acquired. Your broker's annual tax statement shows the same figures: check them against it."
          >
            <table className="w-full whitespace-nowrap text-left text-xs">
              <thead className="table-head">
                <tr>
                  <th className={th}>Ticker</th>
                  <th className={`${th} hidden md:table-cell`}>Name</th>
                  <th className={`${th} text-right`}>Shares</th>
                  <th className={`${th} text-right`}>Lots</th>
                  <th className={`${th} text-right`}>Acquired</th>
                  <th
                    className={`${th} text-right`}
                    title="What you paid for the shares still held, buy fees included (average cost)"
                  >
                    Acquisition cost
                  </th>
                  <th className={`${th} text-right`}>Close</th>
                  <th className={`${th} text-right`}>Market value</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {s.holdings.length === 0 && <Empty cols={8}>No shares held.</Empty>}
                {s.holdings.map((h) => (
                  <tr key={h.ticker}>
                    <td className={`${td} font-semibold`}>
                      {h.ticker}
                      <TickerName name={h.name} />
                    </td>
                    <td className="hidden max-w-56 truncate px-3 py-1.5 text-muted md:table-cell">
                      {h.name}
                    </td>
                    <td className={`${td} text-right`}>
                      {hide ? '••••' : fmtPrice(h.shares)}
                    </td>
                    <td className={`${td} text-right text-muted`}>
                      {hide ? '••' : fmtPrice(h.shares / lotSize)}
                    </td>
                    <td className={`${td} text-right`}>{h.acquired_year}</td>
                    <td className={`${td} text-right font-medium`}>{rp(h.cost)}</td>
                    <td className={`${td} text-right text-muted`}>{fmtPrice(h.close)}</td>
                    <td className={`${td} text-right`}>{rp(h.market_value)}</td>
                  </tr>
                ))}
              </tbody>
              <Total
                cols={5}
                nameCol
                values={[rp(s.totals.cost), '', rp(s.totals.market_value)]}
              />
            </table>
          </Section>

          <Section
            title={`Cash dividends in ${s.year}`}
            hint={`SPT: income subject to final tax (or exempt income, if you reinvested the dividends in Indonesia). Tax at your rate in Settings → Investing (${s.dividend_tax_pct}%). Listed by ex-date: one paid in early January can belong to the next year on your broker's statement.`}
          >
            <table className="w-full whitespace-nowrap text-left text-xs">
              <thead className="table-head">
                <tr>
                  <th className={th}>Ex-date</th>
                  <th className={th}>Ticker</th>
                  <th className={`${th} text-right`}>Shares</th>
                  <th className={`${th} text-right`}>Per share</th>
                  <th className={`${th} text-right`}>Gross</th>
                  <th className={`${th} text-right`}>Tax</th>
                  <th className={`${th} text-right`}>Net</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {s.dividends.length === 0 && <Empty cols={7}>No cash dividends.</Empty>}
                {s.dividends.map((d) => (
                  <tr key={`${d.ticker}-${d.ex_date}`}>
                    <td className={td}>{fmtDay(d.ex_date)}</td>
                    <td className={`${td} font-semibold`}>{d.ticker}</td>
                    <td className={`${td} text-right`}>
                      {hide ? '••••' : fmtPrice(d.shares)}
                    </td>
                    <td className={`${td} text-right text-muted`}>
                      {fmtPrice(d.per_share)}
                    </td>
                    <td className={`${td} text-right`}>{rp(d.gross)}</td>
                    <td className={`${td} text-right text-muted`}>{rp(d.tax)}</td>
                    <td className={`${td} text-right font-medium`}>{rp(d.net)}</td>
                  </tr>
                ))}
              </tbody>
              <Total
                cols={4}
                values={[
                  rp(s.totals.dividends_gross),
                  rp(s.totals.dividends_tax),
                  rp(s.totals.dividends_net),
                ]}
              />
            </table>
          </Section>

          <Section
            title={`Share sales in ${s.year}`}
            hint="SPT: income subject to final tax. Sales on IDX are taxed 0.1% of the sale value, withheld by your broker (it is part of the sell fees you recorded); the gain isn't taxed again."
          >
            <table className="w-full whitespace-nowrap text-left text-xs">
              <thead className="table-head">
                <tr>
                  <th className={th}>Ticker</th>
                  <th className={`${th} hidden md:table-cell`}>Name</th>
                  <th className={`${th} text-right`}>Shares</th>
                  <th className={`${th} text-right`}>Sale value</th>
                  <th className={`${th} text-right`}>Final tax 0.1%</th>
                  <th className={`${th} text-right`}>Fees (incl. tax)</th>
                  <th className={`${th} text-right`}>Realized P/L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {s.sales.length === 0 && <Empty cols={7}>No sales.</Empty>}
                {s.sales.map((x) => (
                  <tr key={x.ticker}>
                    <td className={`${td} font-semibold`}>
                      {x.ticker}
                      <TickerName name={x.name} />
                    </td>
                    <td className="hidden max-w-56 truncate px-3 py-1.5 text-muted md:table-cell">
                      {x.name}
                    </td>
                    <td className={`${td} text-right`}>
                      {hide ? '••••' : fmtPrice(x.shares)}
                    </td>
                    <td className={`${td} text-right font-medium`}>{rp(x.proceeds)}</td>
                    <td className={`${td} text-right`}>{rp(x.sales_tax)}</td>
                    <td className={`${td} text-right text-muted`}>{rp(x.fees)}</td>
                    <td className={`${td} text-right`}>{rp(x.realized_pl)}</td>
                  </tr>
                ))}
              </tbody>
              <Total
                cols={3}
                nameCol
                values={[
                  rp(s.totals.proceeds),
                  rp(s.totals.sales_tax),
                  '',
                  rp(s.totals.realized_pl),
                ]}
              />
            </table>
          </Section>

          <p className="text-2xs text-subtle">
            Worked out from the transactions recorded in Bursa, including rights issues
            and bonus shares you recorded: trades not recorded here aren&apos;t included.
            Shares and prices are as they were then, before any later split. This is a
            worksheet, not tax advice.
          </p>
        </div>
      )}
    </main>
  )
}

function Section({
  title,
  hint,
  children,
}: {
  title: string
  hint: string
  children: ReactNode
}) {
  return (
    <section className="break-inside-avoid">
      <h3 className="text-xs font-semibold text-ink">{title}</h3>
      <p className="mb-2 mt-0.5 max-w-3xl text-2xs text-subtle">{hint}</p>
      <div className="surface relative overflow-x-auto">{children}</div>
    </section>
  )
}

function Empty({ cols, children }: { cols: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={cols} className="px-3 py-4 text-center text-subtle">
        {children}
      </td>
    </tr>
  )
}

/**
 * A totals row: `cols` label columns, then the values. `nameCol`: one of those
 * is the Name column, hidden on phones, so the label spans one less there.
 */
function Total({
  cols,
  values,
  nameCol = false,
}: {
  cols: number
  values: string[]
  nameCol?: boolean
}) {
  return (
    <tfoot className="border-t border-line-strong font-semibold">
      <tr>
        <td colSpan={nameCol ? cols - 1 : cols} className="px-3 py-2">
          Total
        </td>
        {nameCol && <td className="hidden md:table-cell" />}
        {values.map((v, i) => (
          <td key={i} className={`${td} text-right`}>
            {v}
          </td>
        ))}
      </tr>
    </tfoot>
  )
}
