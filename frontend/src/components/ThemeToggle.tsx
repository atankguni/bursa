import { Monitor, Moon, Sun } from 'lucide-react'
import { useTheme, type ThemeChoice } from '../lib/theme'

const OPTIONS: { value: ThemeChoice; label: string; Icon: typeof Sun }[] = [
  { value: 'system', label: 'System', Icon: Monitor },
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
]

// Compact segmented control; default choice is "system".
export default function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="flex overflow-hidden rounded-lg ring-1 ring-line">
      {OPTIONS.map(({ value, label, Icon }) => (
        <button
          key={value}
          onClick={() => setTheme(value)}
          title={label}
          aria-label={`${label} theme`}
          className={`px-2 py-1.5 transition ${
            theme === value ? 'bg-active text-ink' : 'text-muted hover:text-ink'
          }`}
        >
          <Icon size={15} />
        </button>
      ))}
    </div>
  )
}
