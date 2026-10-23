/** Appearance: theme, accent, density and accessibility (this device). */
import { Check } from 'lucide-react'
import {
  ACCENTS,
  useSettings,
  type Accent,
  type Density,
  type Theme,
} from '../../lib/settings'
import { ListRow, Rows, Segmented, Switch } from './controls'

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

export default function AppearanceSection() {
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
