import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'

interface Props {
  options: string[]
  selected: string[]
  onChange: (next: string[]) => void
}

/**
 * Checkbox dropdown for picking several indices at once.
 * At least one index always stays selected.
 */
export default function IndexMultiSelect({ options, selected, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close the popover on any click outside of it.
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  const toggle = (idx: string) => {
    if (selected.includes(idx)) {
      if (selected.length === 1) return // never allow an empty selection
      onChange(selected.filter((s) => s !== idx))
    } else {
      // Keep the options' canonical order.
      onChange(options.filter((o) => selected.includes(o) || o === idx))
    }
  }

  const label = selected.length <= 2 ? selected.join(', ') : `${selected.length} indices`

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded bg-panelalt/70 py-1 pl-3 pr-2 text-xs font-medium text-ink ring-1 ring-line transition hover:bg-panelalt"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="max-w-[14rem] truncate">{label}</span>
        <ChevronDown
          size={13}
          className={`text-muted transition ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div className="absolute left-0 z-20 mt-1 w-48 animate-fade-in overflow-hidden rounded-md bg-panel p-1 shadow-pop ring-1 ring-line">
          {options.map((opt) => {
            const active = selected.includes(opt)
            return (
              <label
                key={opt}
                className="flex cursor-pointer items-center gap-2 rounded px-2.5 py-1.5 text-xs transition hover:bg-panelalt"
              >
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => toggle(opt)}
                  className="h-3.5 w-3.5 accent-bull"
                />
                <span className={active ? 'text-ink' : 'text-muted'}>{opt}</span>
              </label>
            )
          })}
        </div>
      )}
    </div>
  )
}
