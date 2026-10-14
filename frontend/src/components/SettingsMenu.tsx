import { useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import {
  Columns3,
  Palette,
  RotateCcw,
  Settings as SettingsIcon,
  SlidersHorizontal,
  X,
} from 'lucide-react'
import { DEFAULT_INDEXES } from '../api'
import { useSettings, type Density, type NumberFormat, type Theme } from '../lib/settings'

const HOME_COLUMNS = [
  { key: 'index', label: 'Index' },
  { key: 'change', label: 'Change' },
  { key: 'pct', label: '%' },
  { key: 'signal', label: 'Signal' },
  { key: 'volume', label: 'Volume' },
]
const WATCHLIST_COLUMNS = [
  { key: 'name', label: 'Name' },
  { key: 'signal', label: 'Signal' },
  { key: 'shares', label: 'Shares' },
  { key: 'marketCap', label: 'Market Cap' },
  { key: 'revenue', label: 'Revenue' },
  { key: 'netIncome', label: 'Net Income' },
  { key: 'assets', label: 'Assets' },
  { key: 'liabilities', label: 'Liabilities' },
  { key: 'equity', label: 'Equity' },
  { key: 'pbv', label: 'PBV' },
  { key: 'roe', label: 'RoE' },
]

// --------------------------------------------------------------------------- //
// Small controls
// --------------------------------------------------------------------------- //

function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
}) {
  return (
    <div className="inline-flex rounded-md bg-panelalt/70 p-0.5 ring-1 ring-line-strong">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`rounded px-2.5 py-1 text-xs font-medium transition ${
            value === o.value
              ? 'bg-panel text-ink shadow-card ring-1 ring-line-strong'
              : 'text-muted hover:text-ink'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative h-5 w-9 shrink-0 rounded transition-colors ${
        checked ? 'bg-bull' : 'bg-active'
      }`}
    >
      <span
        className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-4' : ''
        }`}
      />
    </button>
  )
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded px-2.5 py-1 text-xs font-medium ring-1 transition ${
        active
          ? 'bg-bull/15 text-bull ring-bull/30'
          : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
      }`}
    >
      {label}
    </button>
  )
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Palette
  title: string
  children: ReactNode
}) {
  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-1.5 px-1 text-[10px] font-semibold uppercase tracking-wider text-subtle">
        <Icon size={12} /> {title}
      </h3>
      <div className="divide-y divide-line overflow-hidden rounded-md bg-panelalt/40 ring-1 ring-line">
        {children}
      </div>
    </section>
  )
}

function ListRow({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-4 px-3.5 py-2.5">
      <div className="min-w-0">
        <div className="text-xs font-medium text-ink">{label}</div>
        {hint && <div className="mt-0.5 text-[10px] text-subtle">{hint}</div>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

function StackedRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-2 px-3.5 py-3">
      <div className="text-xs font-medium text-ink">{label}</div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Settings modal
// --------------------------------------------------------------------------- //

export default function SettingsMenu() {
  const { settings, update, reset } = useSettings()
  const [open, setOpen] = useState(false)

  const toggleColumn = (table: 'home' | 'watchlist', key: string) => {
    const current = settings.hiddenColumns[table]
    const next = current.includes(key)
      ? current.filter((k) => k !== key)
      : [...current, key]
    update({ hiddenColumns: { ...settings.hiddenColumns, [table]: next } })
  }

  const toggleIndex = (idx: string) => {
    const cur = settings.defaultIndexes
    if (cur.includes(idx)) {
      if (cur.length === 1) return // keep at least one
      update({ defaultIndexes: cur.filter((i) => i !== idx) })
    } else {
      update({
        defaultIndexes: DEFAULT_INDEXES.filter((i) => cur.includes(i) || i === idx),
      })
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title="Settings"
        aria-label="Settings"
        className="rounded p-2 text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
      >
        <SettingsIcon size={15} />
      </button>

      {open &&
        createPortal(
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          >
            <div
              className="flex max-h-[85vh] w-full max-w-lg animate-fade-in flex-col overflow-hidden rounded-md bg-panel shadow-pop ring-1 ring-line"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-md bg-gradient-to-br from-bull to-emerald-600 p-2 text-white shadow-card">
                    <SettingsIcon size={16} strokeWidth={2.5} />
                  </div>
                  <div>
                    <h2 className="text-sm font-semibold tracking-tight">Settings</h2>
                    <p className="text-[11px] text-subtle">
                      Preferences saved in this browser
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setOpen(false)}
                  className="rounded p-1.5 text-muted transition hover:bg-panelalt hover:text-ink"
                  aria-label="Close"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Body */}
              <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
                <Section icon={Palette} title="Appearance">
                  <ListRow label="Theme">
                    <Segmented<Theme>
                      value={settings.theme}
                      onChange={(v) => update({ theme: v })}
                      options={[
                        { value: 'system', label: 'System' },
                        { value: 'light', label: 'Light' },
                        { value: 'dark', label: 'Dark' },
                      ]}
                    />
                  </ListRow>
                  <ListRow label="Density">
                    <Segmented<Density>
                      value={settings.density}
                      onChange={(v) => update({ density: v })}
                      options={[
                        { value: 'compact', label: 'Compact' },
                        { value: 'medium', label: 'Medium' },
                        { value: 'large', label: 'Large' },
                      ]}
                    />
                  </ListRow>
                  <ListRow label="Reduce motion" hint="Disable pulsing animations">
                    <Switch
                      label="Reduce motion"
                      checked={settings.reduceMotion}
                      onChange={(v) => update({ reduceMotion: v })}
                    />
                  </ListRow>
                  <ListRow label="High contrast" hint="Stronger colours (WCAG AA)">
                    <Switch
                      label="High contrast"
                      checked={settings.highContrast}
                      onChange={(v) => update({ highContrast: v })}
                    />
                  </ListRow>
                </Section>

                <Section icon={SlidersHorizontal} title="Display">
                  <ListRow label="Number format" hint="Volumes & financials">
                    <Segmented<NumberFormat>
                      value={settings.numberFormat}
                      onChange={(v) => update({ numberFormat: v })}
                      options={[
                        { value: 'compact', label: 'Compact' },
                        { value: 'full', label: 'Full' },
                      ]}
                    />
                  </ListRow>
                  <ListRow label="Chart type">
                    <Segmented<'candle' | 'line'>
                      value={settings.chartType}
                      onChange={(v) => update({ chartType: v })}
                      options={[
                        { value: 'candle', label: 'Candle' },
                        { value: 'line', label: 'Line' },
                      ]}
                    />
                  </ListRow>
                  <ListRow label="Chart range">
                    <Segmented<'1d' | '1m'>
                      value={settings.chartRange}
                      onChange={(v) => update({ chartRange: v })}
                      options={[
                        { value: '1d', label: 'Daily' },
                        { value: '1m', label: '1-Min' },
                      ]}
                    />
                  </ListRow>
                  <ListRow label="Auto-refresh" hint="Poll the API for new data">
                    <div className="flex items-center gap-2">
                      <select
                        value={settings.refreshSeconds}
                        disabled={!settings.autoRefresh}
                        onChange={(e) =>
                          update({ refreshSeconds: Number(e.target.value) })
                        }
                        className="rounded bg-panel px-2 py-1 text-xs text-ink ring-1 ring-line-strong disabled:opacity-40"
                      >
                        {[30, 60, 120, 300].map((s) => (
                          <option key={s} value={s}>
                            {s}s
                          </option>
                        ))}
                      </select>
                      <Switch
                        label="Auto-refresh"
                        checked={settings.autoRefresh}
                        onChange={(v) => update({ autoRefresh: v })}
                      />
                    </div>
                  </ListRow>
                  <ListRow label="Colorize changes" hint="Green / red price movement">
                    <Switch
                      label="Colorize changes"
                      checked={settings.colorizeChanges}
                      onChange={(v) => update({ colorizeChanges: v })}
                    />
                  </ListRow>
                </Section>

                <Section icon={Columns3} title="Data">
                  <StackedRow label="Default indices">
                    {DEFAULT_INDEXES.map((idx) => (
                      <Chip
                        key={idx}
                        label={idx}
                        active={settings.defaultIndexes.includes(idx)}
                        onClick={() => toggleIndex(idx)}
                      />
                    ))}
                  </StackedRow>
                  <StackedRow label="Home columns (highlighted = visible)">
                    {HOME_COLUMNS.map((c) => (
                      <Chip
                        key={c.key}
                        label={c.label}
                        active={!settings.hiddenColumns.home.includes(c.key)}
                        onClick={() => toggleColumn('home', c.key)}
                      />
                    ))}
                  </StackedRow>
                  <StackedRow label="Watchlist columns (highlighted = visible)">
                    {WATCHLIST_COLUMNS.map((c) => (
                      <Chip
                        key={c.key}
                        label={c.label}
                        active={!settings.hiddenColumns.watchlist.includes(c.key)}
                        onClick={() => toggleColumn('watchlist', c.key)}
                      />
                    ))}
                  </StackedRow>
                </Section>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between gap-3 border-t border-line bg-panelalt/40 px-5 py-3">
                <span className="text-[11px] text-subtle">Changes apply instantly.</span>
                <button
                  onClick={reset}
                  className="inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
                >
                  <RotateCcw size={13} /> Reset to defaults
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
