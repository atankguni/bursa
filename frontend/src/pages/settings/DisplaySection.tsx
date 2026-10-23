/** Display: number format, charts and auto-refresh (your account). */
import { useSettings, type NumberFormat } from '../../lib/settings'
import { ListRow, Rows, Segmented, Switch } from './controls'

export default function DisplaySection() {
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
