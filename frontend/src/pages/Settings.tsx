import { type ReactNode, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Navigate, NavLink, useParams } from 'react-router-dom'
import {
  Check,
  Columns3,
  Palette,
  RotateCcw,
  Settings as SettingsIcon,
  ShieldCheck,
  SlidersHorizontal,
  TrendingUp,
  Users as UsersIcon,
} from 'lucide-react'
import {
  DEFAULT_INDEXES,
  fetchAuthOptions,
  sendDigestPreview,
  type InvestingStyle,
  type TradingCosts,
} from '../api'
import { useAssistantStatus, usePreferences } from '../hooks'
import { useAuth } from '../lib/auth'
import {
  ACCENTS,
  useSettings,
  type Accent,
  type Density,
  type NumberFormat,
  type Theme,
} from '../lib/settings'
import Security from './Security'
import Users from './Users'

const STYLE_HINT: Record<InvestingStyle, string> = {
  investor: 'Long term · quality & value from yearly fundamentals',
  trader: 'Swing, 1–4 weeks · calm, liquid price action (no fundamentals needed)',
}

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

// Swatch previews only (the real shades are CSS tokens in index.css), so every
// option shows its own colour whatever accent is active.
const ACCENT_SWATCH: Record<Accent, { light: string; dark: string }> = {
  blue: { light: '#2563eb', dark: '#60a5fa' },
  indigo: { light: '#4f46e5', dark: '#818cf8' },
  violet: { light: '#7c3aed', dark: '#a78bfa' },
  graphite: { light: '#334155', dark: '#cbd5e1' },
}

function AccentPicker({
  value,
  theme,
  onChange,
}: {
  value: Accent
  theme: 'light' | 'dark'
  onChange: (v: Accent) => void
}) {
  return (
    <div role="radiogroup" aria-label="Accent colour" className="flex items-center gap-2">
      {ACCENTS.map((a) => {
        const selected = a.value === value
        const color = ACCENT_SWATCH[a.value][theme]
        return (
          <button
            key={a.value}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={a.label}
            title={a.label}
            onClick={() => onChange(a.value)}
            style={{ backgroundColor: color, color }}
            className={`flex h-6 w-6 items-center justify-center rounded-full transition ${
              selected
                ? 'ring-2 ring-current ring-offset-2 ring-offset-panel'
                : 'opacity-80 hover:opacity-100'
            }`}
          >
            {selected && (
              <Check
                size={13}
                strokeWidth={3}
                className={theme === 'dark' ? 'text-app' : 'text-white'}
              />
            )}
          </button>
        )
      })}
    </div>
  )
}

function Switch({
  checked,
  onChange,
  label,
  disabled = false,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-5 w-9 shrink-0 rounded transition-colors disabled:opacity-40 ${
        checked ? 'bg-accent' : 'bg-active'
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
          ? 'bg-accent/15 text-accent ring-accent/30'
          : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
      }`}
    >
      {label}
    </button>
  )
}

const SCOPE_LABEL = {
  account: {
    label: 'Your account',
    hint: 'Saved to your account: the same on all your devices',
  },
  device: {
    label: 'This device',
    hint: 'Saved in this browser only, so each device can differ',
  },
}

/** The rows of one settings group. */
function Rows({ children }: { children: ReactNode }) {
  return (
    <div className="divide-y divide-line overflow-hidden rounded-md bg-panelalt/40 ring-1 ring-line">
      {children}
    </div>
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
// Sections
// --------------------------------------------------------------------------- //

function InvestingSettings() {
  const {
    style,
    setStyle,
    personalData,
    setPersonalData,
    saveChats,
    setSaveChats,
    isSaving,
    error: styleError,
  } = usePreferences()
  const chatDays = useAssistantStatus().data?.chat_days ?? 90
  const onSaveChats = (on: boolean) => {
    if (
      on ||
      window.confirm('Stop saving assistant chats and delete the ones saved so far?')
    ) {
      setSaveChats(on)
    }
  }
  return (
    <Rows>
      <ListRow
        label="Style"
        hint={
          styleError
            ? 'Could not save — try again'
            : isSaving
              ? 'Re-scoring signals…'
              : STYLE_HINT[style]
        }
      >
        <Segmented<InvestingStyle>
          value={style}
          options={[
            { value: 'investor', label: 'Investor' },
            { value: 'trader', label: 'Trader' },
          ]}
          onChange={setStyle}
        />
      </ListRow>
      <ListRow
        label="Assistant sees my portfolio"
        hint="Lets the AI answer about your holdings & watchlist. They are sent to Google Gemini, whose free tier may use prompts for training."
      >
        <Switch
          checked={personalData}
          onChange={setPersonalData}
          label="Assistant sees my portfolio"
        />
      </ListRow>
      <ListRow
        label="Save assistant chats"
        hint={`Continue a chat later or on another device. Each chat is deleted ${chatDays} day${chatDays === 1 ? '' : 's'} after its last message; turning this off deletes them now.`}
      >
        <Switch checked={saveChats} onChange={onSaveChats} label="Save assistant chats" />
      </ListRow>
    </Rows>
  )
}

const COST_FIELDS: {
  key: keyof TradingCosts
  label: string
  hint: string
  max: number
}[] = [
  { key: 'buy_fee_pct', label: 'Buy fee', hint: 'Broker fee + levies', max: 5 },
  {
    key: 'sell_fee_pct',
    label: 'Sell fee',
    hint: 'Includes the 0.1% final tax on share sales',
    max: 5,
  },
  {
    key: 'dividend_tax_pct',
    label: 'Dividend tax',
    hint: '10% final tax for residents (0% if exempt by reinvesting)',
    max: 50,
  },
]

/** The summary email after the close (needs email set up on the server). */
function DigestSettings() {
  const { dailyDigest, setDailyDigest } = usePreferences()
  const { data: options } = useQuery({
    queryKey: ['auth', 'options'],
    queryFn: fetchAuthOptions,
  })
  const emailReady = options?.password_reset_by_email ?? false // email is set up
  const preview = useMutation({ mutationFn: sendDigestPreview })
  const detail = (preview.error as { response?: { data?: { detail?: string } } } | null)
    ?.response?.data?.detail
  return (
    <Rows>
      <ListRow
        label="Daily summary email"
        hint={
          emailReady
            ? 'After the close on trading days: your portfolio’s day, big moves, signal changes and dividends coming up.'
            : 'Needs email to be set up on the server (an admin can do that).'
        }
      >
        <Switch
          checked={dailyDigest}
          onChange={setDailyDigest}
          label="Daily summary email"
          disabled={!emailReady}
        />
      </ListRow>
      {emailReady && (
        <ListRow
          label="Preview"
          hint={
            preview.isSuccess
              ? 'Sent: check your inbox.'
              : (detail ?? 'Email today’s summary to yourself now.')
          }
        >
          <button
            onClick={() => preview.mutate()}
            disabled={preview.isPending}
            className="rounded px-2.5 py-1 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50"
          >
            {preview.isPending ? 'Sending…' : 'Send now'}
          </button>
        </ListRow>
      )}
    </Rows>
  )
}

/** Broker costs: fill in new trades' fees and make the portfolio's returns net. */
function TradingCostSettings() {
  const { tradingCosts, setTradingCosts } = usePreferences()
  const [draft, setDraft] = useState<Record<string, string>>({})
  const save = (key: keyof TradingCosts, max: number) => {
    const raw = draft[key]
    if (raw === undefined) return
    const value = Number(raw.replace(',', '.'))
    setDraft(({ [key]: _, ...rest }) => rest)
    if (raw.trim() !== '' && Number.isFinite(value) && value >= 0 && value <= max) {
      if (value !== tradingCosts[key]) setTradingCosts({ ...tradingCosts, [key]: value })
    }
  }
  return (
    <div className="space-y-2">
      <div>
        <h3 className="text-xs font-semibold text-ink">Trading costs</h3>
        <p className="text-[11px] text-subtle">
          From your broker&apos;s fee schedule. They pre-fill the fee of new transactions,
          and the portfolio shows profit after selling costs and dividends after tax.
        </p>
      </div>
      <Rows>
        {COST_FIELDS.map(({ key, label, hint, max }) => (
          <ListRow key={key} label={label} hint={hint}>
            <span className="inline-flex items-center gap-1.5 text-xs text-muted">
              <input
                inputMode="decimal"
                aria-label={`${label} (%)`}
                value={draft[key] ?? String(tradingCosts[key])}
                onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                onBlur={() => save(key, max)}
                onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                className="w-16 rounded bg-panel px-2 py-1 text-right tabular-nums text-ink ring-1 ring-line-strong outline-none focus:ring-accent"
              />
              %
            </span>
          </ListRow>
        ))}
      </Rows>
    </div>
  )
}

function AppearanceSettings() {
  const { settings, resolvedTheme, update } = useSettings()
  return (
    <Rows>
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
      <ListRow
        label="Accent colour"
        hint={`${ACCENTS.find((a) => a.value === settings.accent)?.label ?? 'Blue'} · buttons, highlights & charts`}
      >
        <AccentPicker
          value={settings.accent}
          theme={resolvedTheme}
          onChange={(v) => update({ accent: v })}
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
    </Rows>
  )
}

function DisplaySettings() {
  const { settings, update } = useSettings()
  return (
    <Rows>
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
            { value: 'line', label: 'Line' },
            { value: 'candle', label: 'Candle' },
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
            onChange={(e) => update({ refreshSeconds: Number(e.target.value) })}
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
    </Rows>
  )
}

function TableSettings() {
  const { settings, update } = useSettings()

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
    <Rows>
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
    </Rows>
  )
}

/** Appearance, display and tables share one reset (lib/settings). */
function ResetSettings() {
  const { reset } = useSettings()
  const onReset = () => {
    if (
      window.confirm('Reset appearance, display and table settings to their defaults?')
    ) {
      reset()
    }
  }
  return (
    <button
      onClick={onReset}
      className="inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
    >
      <RotateCcw size={13} /> Reset appearance, display &amp; tables
    </button>
  )
}

type SectionId = 'investing' | 'appearance' | 'display' | 'tables' | 'security' | 'users'

const SECTIONS: {
  id: SectionId
  label: string
  icon: typeof Palette
  description: string
  scope?: 'account' | 'device'
  adminOnly?: boolean
  wide?: boolean
}[] = [
  {
    id: 'investing',
    label: 'Investing',
    icon: TrendingUp,
    description: 'How signals are scored for you, and what the assistant may see.',
    scope: 'account',
  },
  {
    id: 'appearance',
    label: 'Appearance',
    icon: Palette,
    description: 'Theme, colours and spacing.',
    scope: 'device',
  },
  {
    id: 'display',
    label: 'Display',
    icon: SlidersHorizontal,
    description: 'Numbers, charts and refreshing.',
    scope: 'account',
  },
  {
    id: 'tables',
    label: 'Tables & indices',
    icon: Columns3,
    description: 'Which indices and columns you see first.',
    scope: 'account',
  },
  {
    id: 'security',
    label: 'Security',
    icon: ShieldCheck,
    description: 'Password, two-factor authentication and remembered devices.',
  },
  {
    id: 'users',
    label: 'Users & invites',
    icon: UsersIcon,
    description: 'Invite-only: people join through a link you create here.',
    adminOnly: true,
    wide: true,
  },
]

const navCls = ({ isActive }: { isActive: boolean }) =>
  `flex shrink-0 items-center gap-2 whitespace-nowrap rounded px-2.5 py-1.5 text-xs font-medium transition ${
    isActive
      ? 'bg-panel text-accent shadow-card ring-1 ring-line-strong'
      : 'text-muted hover:bg-panelalt hover:text-ink'
  }`

// --------------------------------------------------------------------------- //
// Settings page: /settings/:section
// --------------------------------------------------------------------------- //

export default function Settings() {
  const { section: id } = useParams()
  const { user, isAdmin } = useAuth()
  const sections = SECTIONS.filter((s) => !s.adminOnly || isAdmin)
  const section = sections.find((s) => s.id === id)
  if (!section) return <Navigate to="/settings/investing" replace />

  return (
    <main className="w-full animate-fade-in px-4 py-4">
      <div className="mb-4 flex items-center gap-2">
        <SettingsIcon size={16} className="text-accent" />
        <h2 className="text-sm font-semibold tracking-tight">Settings</h2>
        <p className="text-[11px] text-subtle">Changes apply instantly</p>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-start">
        {/* Side menu on wide screens, a scrolling row of tabs on phones. */}
        <nav
          aria-label="Settings sections"
          className="-mx-4 flex gap-1 overflow-x-auto px-4 md:sticky md:top-20 md:mx-0 md:w-48 md:shrink-0 md:flex-col md:px-0"
        >
          {sections.map((s) => (
            <NavLink key={s.id} to={`/settings/${s.id}`} className={navCls}>
              <s.icon size={14} /> {s.label}
              {s.id === 'security' && (user?.password_weak || !user?.has_2fa) && (
                <span className="ml-auto rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-400">
                  {user?.password_weak ? 'Weak password' : '2FA off'}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <section
          className={`min-w-0 flex-1 space-y-3 ${section.wide ? '' : 'max-w-3xl'}`}
        >
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold">{section.label}</h3>
              {section.scope && (
                <span
                  title={SCOPE_LABEL[section.scope].hint}
                  className="rounded bg-panelalt px-1.5 py-0.5 text-[10px] font-medium text-subtle ring-1 ring-line"
                >
                  {SCOPE_LABEL[section.scope].label}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted">{section.description}</p>
          </div>

          {section.id === 'investing' && (
            <div className="space-y-5">
              <InvestingSettings />
              <DigestSettings />
              <TradingCostSettings />
            </div>
          )}
          {section.id === 'appearance' && <AppearanceSettings />}
          {section.id === 'display' && <DisplaySettings />}
          {section.id === 'tables' && <TableSettings />}
          {section.id === 'security' && <Security />}
          {section.id === 'users' && <Users />}

          {(section.id === 'appearance' ||
            section.id === 'display' ||
            section.id === 'tables') && (
            <div className="pt-1">
              <ResetSettings />
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
