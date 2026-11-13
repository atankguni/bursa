import { useEffect, useId, useLayoutEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

/**
 * - large: content views (stock detail, charts), 75% of the screen.
 * - form: short forms (a few fields), compact width, as tall as the content.
 * Phones get the full screen either way.
 */
export type ModalSize = 'large' | 'form'

const PANEL: Record<ModalSize, string> = {
  large: 'sm:h-[75vh] sm:w-[75vw] sm:max-w-[1600px]',
  form: 'sm:h-auto sm:max-h-[85vh] sm:w-full sm:max-w-md',
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Open dialogs, innermost last: Escape closes only the top one.
const stack: string[] = []

/**
 * The one dialog shell of the app, so every pop-up behaves the same:
 * - closes with its ✕ button or Escape, never by clicking outside it
 *   (a stray click must not throw away what was typed);
 * - keeps keyboard focus inside while open, and returns it afterwards;
 * - the page behind doesn't scroll.
 */
export default function Modal({
  onClose,
  size = 'large',
  title,
  description,
  icon,
  header,
  label,
  actions,
  footer,
  children,
  bodyClassName = '',
}: {
  onClose: () => void
  size?: ModalSize
  /** Simple header: title (+ description, icon). */
  title?: ReactNode
  description?: ReactNode
  icon?: ReactNode
  /** Custom header content instead of title/description; give `label` then. */
  header?: ReactNode
  /** Accessible name when `title` isn't plain text. */
  label?: string
  /** Buttons next to the close button. */
  actions?: ReactNode
  footer?: ReactNode
  children: ReactNode
  bodyClassName?: string
}) {
  const id = useId()
  const panel = useRef<HTMLDivElement>(null)
  // Latest onClose without re-running the effects below on every render.
  const close = useRef(onClose)
  useLayoutEffect(() => {
    close.current = onClose
  })

  useEffect(() => {
    stack.push(id)
    const opener =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    // Focus the dialog unless a field inside already took it (autoFocus).
    if (!panel.current?.contains(document.activeElement)) panel.current?.focus()

    const body = document.body.style
    const overflow = body.overflow
    body.overflow = 'hidden'

    const onKey = (e: KeyboardEvent) => {
      if (stack[stack.length - 1] !== id) return
      if (e.key === 'Escape' && !e.defaultPrevented) {
        e.preventDefault()
        close.current()
      } else if (e.key === 'Tab' && panel.current) {
        const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
          (el) => el.offsetParent !== null,
        )
        const first = items[0]
        const last = items[items.length - 1]
        if (!first || !last) return e.preventDefault()
        const active = document.activeElement
        if (e.shiftKey && (active === first || active === panel.current)) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && active === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)

    return () => {
      document.removeEventListener('keydown', onKey)
      stack.splice(stack.indexOf(id), 1)
      if (stack.length === 0) body.overflow = overflow
      opener?.focus?.()
    }
  }, [id])

  const titleId = `${id}-title`
  return createPortal(
    // No click handler on the backdrop: only ✕ (or Escape) closes the dialog.
    <div className="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-zinc-950/45 backdrop-blur-sm sm:p-6">
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title && !label ? titleId : undefined}
        aria-label={label}
        tabIndex={-1}
        className={`flex h-full w-full animate-fade-in flex-col overflow-hidden bg-panel shadow-pop outline-hidden ring-1 ring-line sm:rounded-lg ${PANEL[size]}`}
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-line px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))] sm:px-6 sm:py-4">
          <div className="min-w-0 flex-1">
            {header ?? (
              <div className="flex items-center gap-3">
                {icon && (
                  <div className="grid h-9 w-9 place-items-center rounded-sm bg-accent/10 text-accent">
                    {icon}
                  </div>
                )}
                <div className="min-w-0">
                  <h2 id={titleId} className="text-base font-semibold tracking-tight">
                    {title}
                  </h2>
                  {description && <p className="text-xs text-muted">{description}</p>}
                </div>
              </div>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {actions}
            <button
              onClick={onClose}
              aria-label="Close"
              title="Close"
              className="btn btn-ghost btn-icon -mr-1.5"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div
          className={`min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5 ${bodyClassName}`}
        >
          {children}
        </div>

        {footer && (
          <div className="flex shrink-0 items-center justify-between gap-3 border-t border-line bg-panelalt/40 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-6 sm:pb-3">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
