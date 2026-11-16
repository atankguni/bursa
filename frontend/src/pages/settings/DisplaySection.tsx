/** Display: numbers, dates, the start page, charts and auto-refresh (your account). */
import {
  useSettings,
  type DateStyle,
  type NumberFormat,
  type NumberLocale,
  type StartPage,
} from '../../lib/settings'
import { ListRow, Rows, Segmented, Switch } from './controls'

const START_PAGES: StartPage[] = ['home', 'watchlist', 'portfolio']

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
      <ListRow
        label="Number style"
        hint={
          settings.numberLocale === 'id' ? 'Rp 1.234.567 · 12,5%' : 'Rp 1,234,567 · 12.5%'
        }
      >
        <Segmented<NumberLocale>
          value={settings.numberLocale}
          onChange={(v) => update({ numberLocale: v })}
          options={[
            { value: 'en', label: '1,234.5' },
            { value: 'id', label: '1.234,5' },
          ]}
        />
      </ListRow>
      <ListRow label="Dates">
        <Segmented<DateStyle>
          value={settings.dateStyle}
          onChange={(v) => update({ dateStyle: v })}
          options={[
            { value: 'text', label: '16 Nov 2026' },
            { value: 'numeric', label: '16/11/2026' },
          ]}
        />
      </ListRow>
      <ListRow label="Start page" hint="What opens first when you come to Bursa">
        <select
          value={settings.startPage}
          onChange={(e) => {
            const page = START_PAGES.find((x) => x === e.target.value)
            if (page) update({ startPage: page })
          }}
          className="input input-sm w-auto"
        >
          <option value="home">Home</option>
          <option value="watchlist">Watchlist</option>
          <option value="portfolio">Portfolio</option>
        </select>
      </ListRow>
      <ListRow
        label="Hide portfolio amounts on open"
        hint="Amounts start as ••• each time; the eye button shows them"
      >
        <Switch
          label="Hide portfolio amounts on open"
          checked={settings.hideValuesOnOpen}
          onChange={(v) => update({ hideValuesOnOpen: v })}
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
            className="input input-sm w-auto disabled:opacity-40"
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
