/** Investing: style, the assistant's access, the daily email and trading costs (your account). */
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  fetchAuthOptions,
  sendDigestPreview,
  type InvestingStyle,
  type TradingCosts,
} from '../../api'
import { errorDetail } from '../../api/client'
import { useAssistantStatus, usePreferences } from '../../hooks'
import { ListRow, Rows, Segmented, Switch } from './controls'

const STYLE_HINT: Record<InvestingStyle, string> = {
  investor: 'Long term · quality & value from yearly fundamentals',
  trader: 'Swing, 1–4 weeks · calm, liquid price action (no fundamentals needed)',
}

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
  const detail = errorDetail(preview.error)
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
            className="rounded-sm px-2.5 py-1 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50"
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
                className="w-16 rounded-sm bg-panel px-2 py-1 text-right tabular-nums text-ink ring-1 ring-line-strong outline-hidden focus:ring-accent"
              />
              %
            </span>
          </ListRow>
        ))}
      </Rows>
    </div>
  )
}

export default function InvestingSection() {
  return (
    <div className="space-y-5">
      <InvestingSettings />
      <DigestSettings />
      <TradingCostSettings />
    </div>
  )
}
