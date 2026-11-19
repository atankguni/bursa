import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ChevronDown, SlidersHorizontal } from 'lucide-react'
import { MA_COLORS, type Indicators } from '../StockChart'

const ITEMS: { key: keyof Indicators; label: string; hint: string }[] = [
  { key: 'ma20', label: 'MA20', hint: 'Average close of the last 20 days' },
  { key: 'ma50', label: 'MA50', hint: 'Average close of the last 50 days' },
  { key: 'ma200', label: 'MA200', hint: 'Average close of the last 200 days' },
  { key: 'volume', label: 'Volume', hint: 'Shares traded per bar' },
  { key: 'rsi', label: 'RSI', hint: 'Momentum, 0–100; above 70 hot, below 30 cold' },
]

/** One dropdown for the chart's extras, each with the colour it's drawn in. */
export default function IndicatorMenu({
  ind,
  setInd,
  vsIhsg,
  setVsIhsg,
}: {
  ind: Indicators
  setInd: (next: (prev: Indicators) => Indicators) => void
  /** The IHSG overlay; omit where it doesn't apply (minute bars). */
  vsIhsg?: boolean | undefined
  setVsIhsg?: ((next: (prev: boolean) => boolean) => void) | undefined
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && e.target instanceof Node && !ref.current.contains(e.target))
        setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  const count = ITEMS.filter((i) => ind[i.key]).length + (setVsIhsg && vsIhsg ? 1 : 0)

  return (
    <div
      ref={ref}
      className="relative"
      onKeyDown={(e) => {
        // Escape closes the menu, not the dialog around it.
        if (e.key === 'Escape' && open) {
          e.preventDefault()
          setOpen(false)
        }
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="btn btn-secondary h-8 gap-1.5 px-2.5 text-xs"
      >
        <SlidersHorizontal size={13} aria-hidden />
        Indicators
        {count > 0 && (
          <span className="rounded-sm bg-accent/15 px-1.5 text-2xs font-semibold text-accent">
            {count}
          </span>
        )}
        <ChevronDown
          size={13}
          className={`text-muted transition ${open ? 'rotate-180' : ''}`}
          aria-hidden
        />
      </button>

      {open && (
        <div
          role="group"
          aria-label="Chart indicators"
          className="absolute left-0 z-20 mt-1 w-64 animate-fade-in rounded-md bg-panel p-1 shadow-pop ring-1 ring-line"
        >
          {ITEMS.map((item) => (
            <Row
              key={item.key}
              label={item.label}
              hint={item.hint}
              checked={ind[item.key]}
              onChange={() => setInd((s) => ({ ...s, [item.key]: !s[item.key] }))}
              swatch={
                item.key === 'volume' ? (
                  <span className="flex h-2.5 w-3 items-end gap-px" aria-hidden>
                    <span className="h-1.5 w-1 bg-subtle" />
                    <span className="h-2.5 w-1 bg-subtle" />
                    <span className="h-1 w-1 bg-subtle" />
                  </span>
                ) : (
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${item.key === 'rsi' ? 'bg-accent' : ''}`}
                    style={
                      item.key === 'rsi' ? undefined : { background: MA_COLORS[item.key] }
                    }
                    aria-hidden
                  />
                )
              }
            />
          ))}
          {setVsIhsg && (
            <>
              <div className="my-1 border-t border-line" />
              <Row
                label="vs IHSG"
                hint="Both in % change from the left edge of the chart"
                checked={vsIhsg ?? false}
                onChange={() => setVsIhsg((v) => !v)}
                swatch={
                  <span
                    className="w-3 border-t-2 border-dashed border-subtle"
                    aria-hidden
                  />
                }
              />
            </>
          )}
        </div>
      )}
    </div>
  )
}

function Row({
  label,
  hint,
  checked,
  onChange,
  swatch,
}: {
  label: string
  hint: string
  checked: boolean
  onChange: () => void
  swatch: ReactNode
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5 rounded-sm px-2.5 py-1.5 transition hover:bg-panelalt">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="mt-0.5 h-3.5 w-3.5 accent-accent"
      />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2 text-xs font-medium text-ink">
          {swatch}
          {label}
        </span>
        <span className="block text-2xs text-muted">{hint}</span>
      </span>
    </label>
  )
}
