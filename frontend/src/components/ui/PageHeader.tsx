import type { ReactNode } from 'react'

/** A page's title row: title and a short line under it, actions on the right. */
export default function PageHeader({
  title,
  subtitle,
  actions,
  children,
}: {
  title: ReactNode
  subtitle?: ReactNode | undefined
  actions?: ReactNode | undefined
  /** Extra content under the title (filters, tabs). */
  children?: ReactNode
}) {
  return (
    <div className="mb-5 lg:mb-6">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
        <div className="min-w-0">
          <h2 className="page-title">{title}</h2>
          {subtitle && <p className="page-sub">{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </div>
  )
}
