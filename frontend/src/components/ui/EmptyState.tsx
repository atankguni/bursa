import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

/** A friendly "nothing here yet" with an optional next step. */
export default function EmptyState({
  icon: Icon,
  title,
  children,
  action,
}: {
  icon: LucideIcon
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <span className="mb-3 grid h-11 w-11 place-items-center rounded-full bg-panelalt text-muted">
        <Icon size={20} />
      </span>
      <p className="text-sm font-medium text-ink">{title}</p>
      {children && <p className="mt-1 max-w-sm text-xs text-muted">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
