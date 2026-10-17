interface Option<T extends string> {
  value: T
  label: string
}

/** Underline sub-navigation, visually subordinate to the main tab bar. */
export default function SubTabs<T extends string>({
  options,
  value,
  onChange,
}: {
  options: Option<T>[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="flex gap-4 border-b border-line" role="tablist">
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={`-mb-px border-b-2 px-0.5 pb-2 text-xs font-medium transition ${
              active
                ? 'border-accent text-ink'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
