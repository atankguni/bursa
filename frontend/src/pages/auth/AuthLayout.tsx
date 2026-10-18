import type { InputHTMLAttributes, ReactNode } from 'react'

export const inputCls =
  'w-full rounded bg-panelalt px-3 py-2 text-sm text-ink ring-1 ring-line-strong outline-none focus:ring-accent'
export const primaryBtn =
  'w-full rounded bg-accent px-3 py-2 text-sm font-medium text-accent-ink transition hover:opacity-90 disabled:opacity-50'

/** Centered card used by every signed-out screen. */
export default function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string
  subtitle?: ReactNode
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <div className="flex min-h-full items-center justify-center bg-app px-4 py-12 text-ink">
      <div className="w-full max-w-sm">
        <div className="rounded-md bg-panel p-6 shadow-card ring-1 ring-line">
          <h1 className="text-base font-semibold">{title}</h1>
          {subtitle && <p className="mt-1 text-xs text-muted">{subtitle}</p>}
          <div className="mt-5">{children}</div>
        </div>
        {footer && <div className="mt-4 text-center text-xs text-muted">{footer}</div>}
      </div>
    </div>
  )
}

export function Field({
  label,
  hint,
  ...input
}: { label: string; hint?: ReactNode } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted">{label}</span>
      <input {...input} className={inputCls} />
      {hint && <span className="mt-1 block text-[11px] text-subtle">{hint}</span>}
    </label>
  )
}

export function FormError({ children }: { children: ReactNode }) {
  return children ? (
    <p role="alert" className="text-xs text-bear">
      {children}
    </p>
  ) : null
}
