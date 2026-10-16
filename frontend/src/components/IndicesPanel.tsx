import { useMemo, useState } from 'react'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import type { MarketIndex } from '../api'
import { useIndices } from '../hooks'
import { fmtPct, fmtPrice, fmtShortDateTime } from '../lib/format'
import { useSettings } from '../lib/settings'
import IndexChartModal from './IndexChartModal'
import SubTabs from './SubTabs'

const HEADLINE = ['COMPOSITE', 'LQ45', 'IDX30', 'JII']
const GROUPS = [
  'Benchmark',
  'Sharia',
  'Dividend & SOE',
  'Thematic & ESG',
  'Sector',
  'Board',
]

/** Background tint that deepens with the size of the move (sign shown separately). */
function useTint() {
  const { settings } = useSettings()
  return (pct: number | null) => {
    if (!settings.colorizeChanges || pct == null || pct === 0) return undefined
    const alpha = 0.06 + Math.min(Math.abs(pct) / 4, 1) * 0.22
    return `rgb(var(${pct > 0 ? '--c-bull' : '--c-bear'}) / ${alpha.toFixed(3)})`
  }
}

function Change({ pct, change }: { pct: number | null; change?: number | null }) {
  const { settings } = useSettings()
  if (pct == null) return <span className="text-subtle">—</span>
  const tone =
    !settings.colorizeChanges || pct === 0
      ? 'text-muted'
      : pct > 0
        ? 'text-bull'
        : 'text-bear'
  return (
    <span className={`inline-flex items-center gap-0.5 font-medium tabular-nums ${tone}`}>
      {pct >= 0 ? (
        <ArrowUpRight size={12} aria-hidden />
      ) : (
        <ArrowDownRight size={12} aria-hidden />
      )}
      {change != null && (
        <>
          {change > 0 ? '+' : ''}
          {fmtPrice(change)}{' '}
        </>
      )}
      {change != null ? `(${fmtPct(pct)})` : fmtPct(pct)}
    </span>
  )
}

/** IDX stock indices (indeks saham): headline cards + grouped, tinted tiles. */
export default function IndicesPanel() {
  const { data: indices = [], isLoading } = useIndices()
  const [group, setGroup] = useState('Benchmark')
  const [byChange, setByChange] = useState(false)
  const [selected, setSelected] = useState<MarketIndex | null>(null)
  const tint = useTint()

  const byCode = useMemo(() => new Map(indices.map((i) => [i.code, i])), [indices])
  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const i of indices) c[i.group] = (c[i.group] ?? 0) + 1
    return c
  }, [indices])
  const tiles = useMemo(() => {
    const list = indices.filter((i) => i.group === group)
    return byChange
      ? [...list].sort((a, b) => (b.change_percent ?? -999) - (a.change_percent ?? -999))
      : list
  }, [indices, group, byChange])
  const updated = indices.reduce<string | null>(
    (latest, i) =>
      i.updated_at && (!latest || i.updated_at > latest) ? i.updated_at : latest,
    null,
  )

  return (
    <section className="surface p-4" aria-labelledby="indices-title">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 id="indices-title" className="text-xs font-semibold tracking-tight">
            Stock indices <span className="font-normal text-subtle">· Indeks saham</span>
          </h3>
          <p className="text-[10px] text-subtle">
            {indices.length} IDX indices · click one for its chart
          </p>
        </div>
        {updated && (
          <span className="text-[10px] text-subtle">
            Updated {fmtShortDateTime(updated)}
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-xs text-subtle">Loading indices…</div>
      ) : (
        <>
          {/* Headline indices */}
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {HEADLINE.map((code) => byCode.get(code))
              .filter((i): i is MarketIndex => !!i)
              .map((i) => (
                <button
                  key={i.code}
                  onClick={() => setSelected(i)}
                  className="rounded-md px-3 py-2.5 text-left ring-1 ring-line transition hover:ring-line-strong"
                  style={{ backgroundColor: tint(i.change_percent) }}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-[11px] font-semibold text-ink">
                      {i.code === 'COMPOSITE' ? 'IHSG' : i.code}
                    </span>
                    <span className="truncate text-[10px] text-subtle">{i.name}</span>
                  </div>
                  <div className="mt-1 text-lg font-semibold tabular-nums text-ink">
                    {fmtPrice(i.last)}
                  </div>
                  <div className="text-[11px]">
                    <Change pct={i.change_percent} change={i.change} />
                  </div>
                </button>
              ))}
          </div>

          {/* Grouped tiles: tabs keep 33 indices from becoming one long list. */}
          <div className="mt-4 flex flex-wrap items-end justify-between gap-2">
            <div className="max-w-full overflow-x-auto">
              <SubTabs
                options={GROUPS.map((g) => ({
                  value: g,
                  label: `${g} (${counts[g] ?? 0})`,
                }))}
                value={group}
                onChange={setGroup}
              />
            </div>
            <label className="flex items-center gap-1.5 pb-2 text-[11px] text-subtle">
              <input
                type="checkbox"
                checked={byChange}
                onChange={(e) => setByChange(e.target.checked)}
                className="accent-current"
              />
              Sort by change
            </label>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
            {tiles.map((i) => (
              <button
                key={i.code}
                onClick={() => setSelected(i)}
                aria-label={`${i.name} (${i.code}): ${fmtPrice(i.last)}, ${
                  i.change_percent == null ? 'no change data' : fmtPct(i.change_percent)
                }`}
                className="min-w-0 rounded-md px-2.5 py-2 text-left ring-1 ring-line transition hover:ring-line-strong"
                style={{ backgroundColor: tint(i.change_percent) }}
              >
                <div className="truncate text-[11px] font-semibold text-ink">
                  {i.code}
                </div>
                <div className="truncate text-[10px] text-subtle" title={i.name}>
                  {i.name}
                </div>
                <div className="mt-1 flex items-baseline justify-between gap-1">
                  <span className="text-xs tabular-nums text-ink">
                    {fmtPrice(i.last)}
                  </span>
                  <span className="text-[11px]">
                    <Change pct={i.change_percent} />
                  </span>
                </div>
              </button>
            ))}
          </div>
        </>
      )}

      {selected && <IndexChartModal index={selected} onClose={() => setSelected(null)} />}
    </section>
  )
}
