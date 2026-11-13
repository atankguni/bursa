import type { ReactNode } from 'react'

const VALUE_SIZE = {
  hero: 'text-3xl sm:text-4xl font-semibold tracking-tight',
  lg: 'text-xl font-semibold tracking-tight',
  md: 'text-base font-semibold',
} as const

/** A labelled number: label above, value, an optional line under it. */
export default function Stat({
  label,
  value,
  sub,
  tone = 'text-ink',
  size = 'md',
  title,
}: {
  label: ReactNode
  value: ReactNode
  sub?: ReactNode | undefined
  tone?: string | undefined
  size?: keyof typeof VALUE_SIZE | undefined
  title?: string | undefined
}) {
  return (
    <div className="min-w-0" title={title}>
      <div className="eyebrow">{label}</div>
      <div className={`mt-1 tabular-nums ${VALUE_SIZE[size]} ${tone}`}>{value}</div>
      {sub && <div className="mt-0.5 text-2xs text-subtle">{sub}</div>}
    </div>
  )
}
