import type { InputHTMLAttributes, ReactNode } from 'react'
import { Activity } from 'lucide-react'

export const inputCls = 'input'
export const primaryBtn = 'btn btn-primary h-9 w-full text-sm'

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
    <div className="relative flex min-h-full items-center justify-center overflow-hidden bg-app px-4 py-12 text-ink">
      {/* A soft glow in the accent colour behind the card. */}
      <div
        aria-hidden
        className="pointer-events-none absolute top-[-20%] left-1/2 h-[36rem] w-[36rem] -translate-x-1/2 rounded-full bg-accent/10 blur-3xl"
      />
      <div className="relative w-full max-w-sm animate-fade-in">
        <div className="mb-6 flex items-center justify-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-sm bg-accent text-accent-ink shadow-card">
            <Activity size={18} strokeWidth={2.75} />
          </span>
          <span className="text-lg font-semibold tracking-tight">Bursa</span>
        </div>
        <div className="rounded-lg bg-panel p-6 shadow-pop ring-1 ring-line sm:p-8">
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1.5 text-xs text-muted">{subtitle}</p>}
          <div className="mt-6">{children}</div>
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
      <span className="field-label">{label}</span>
      <input {...input} className={inputCls} />
      {hint && <span className="mt-1 block text-2xs text-subtle">{hint}</span>}
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
