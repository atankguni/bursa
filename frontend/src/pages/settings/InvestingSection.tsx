/** Investing: style, the assistant's access, the benchmark, risk limits, trades and costs (your account). */
import { useState } from 'react'
import {
  type Benchmark,
  type InvestingStyle,
  type RiskLimits,
  type TradingCosts,
} from '../../api'
import { BENCHMARKS, useAssistantStatus, usePreferences } from '../../hooks'
import { useSettings, type TradeUnit } from '../../lib/settings'
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
        <p className="text-2xs text-subtle">
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
                className="input input-sm w-20 text-right tabular-nums"
              />
              %
            </span>
          </ListRow>
        ))}
      </Rows>
    </div>
  )
}

/** A percentage typed in a small box, saved when it loses focus. */
function PctInput({
  label,
  value,
  min,
  max,
  onSave,
}: {
  label: string
  value: number
  min: number
  max: number
  onSave: (v: number) => void
}) {
  const [draft, setDraft] = useState<string | null>(null)
  const save = () => {
    if (draft === null) return
    const v = Number(draft.replace(',', '.'))
    setDraft(null)
    if (
      draft.trim() !== '' &&
      Number.isFinite(v) &&
      v >= min &&
      v <= max &&
      v !== value
    ) {
      onSave(v)
    }
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <input
        inputMode="decimal"
        aria-label={`${label} (%)`}
        value={draft ?? String(value)}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
        className="input input-sm w-20 text-right tabular-nums"
      />
      %
    </span>
  )
}

/** What the portfolio is compared with, when it warns about concentration, and trade entry. */
function PortfolioSettings() {
  const { benchmark, setBenchmark, riskLimits, setRiskLimits } = usePreferences()
  const { settings, update } = useSettings()
  const setLimit = (key: keyof RiskLimits, v: number) =>
    setRiskLimits({ ...riskLimits, [key]: v })
  return (
    <div className="space-y-2">
      <div>
        <h3 className="text-xs font-semibold text-ink">Portfolio</h3>
        <p className="text-2xs text-subtle">
          The index your returns are compared with, and when the risk view warns that too
          much sits in one place.
        </p>
      </div>
      <Rows>
        <ListRow label="Compare with" hint="On the portfolio chart and its summary">
          <Segmented<Benchmark>
            value={benchmark}
            options={BENCHMARKS}
            onChange={setBenchmark}
          />
        </ListRow>
        <ListRow label="One stock limit" hint="Warn when one holding is more than this">
          <PctInput
            label="One stock limit"
            value={riskLimits.stock_pct}
            min={5}
            max={100}
            onSave={(v) => setLimit('stock_pct', v)}
          />
        </ListRow>
        <ListRow label="One sector limit" hint="Warn when one sector is more than this">
          <PctInput
            label="One sector limit"
            value={riskLimits.sector_pct}
            min={5}
            max={100}
            onSave={(v) => setLimit('sector_pct', v)}
          />
        </ListRow>
        <ListRow label="Enter trades in" hint="1 lot = 100 shares">
          <Segmented<TradeUnit>
            value={settings.tradeUnit}
            onChange={(v) => update({ tradeUnit: v })}
            options={[
              { value: 'lots', label: 'Lots' },
              { value: 'shares', label: 'Shares' },
            ]}
          />
        </ListRow>
      </Rows>
    </div>
  )
}

export default function InvestingSection() {
  return (
    <div className="space-y-5">
      <InvestingSettings />
      <PortfolioSettings />
      <TradingCostSettings />
    </div>
  )
}
