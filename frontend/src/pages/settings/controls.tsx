/** Form controls shared by the settings sections. */
import { type ReactNode } from 'react'

export function Segmented<T extends string>({
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

export function Switch({
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

export function Chip({
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

/** The rows of one settings group. */
export function Rows({ children }: { children: ReactNode }) {
  return (
    <div className="divide-y divide-line overflow-hidden rounded-md bg-panelalt/40 ring-1 ring-line">
      {children}
    </div>
  )
}

export function ListRow({
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

export function StackedRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-2 px-3.5 py-3">
      <div className="text-xs font-medium text-ink">{label}</div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  )
}
