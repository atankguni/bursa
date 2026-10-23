/** Tables & indices: the default indices and the visible columns (your account). */
import { DEFAULT_INDEXES } from '../../api'
import { useSettings } from '../../lib/settings'
import { Chip, Rows, StackedRow } from './controls'

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

export default function TablesSection() {
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
