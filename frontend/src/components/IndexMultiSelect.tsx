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

  const label =
    selected.length <= 2 ? selected.join(', ') : `${selected.length} indices`

  return (
    <div ref={ref} className="relative ml-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg bg-panelalt py-1.5 pl-3 pr-2 text-sm text-slate-100 ring-1 ring-slate-700 transition hover:bg-slate-700"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="max-w-[16rem] truncate">{label}</span>
        <ChevronDown
          size={14}
          className={`text-slate-400 transition ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div className="absolute left-0 z-20 mt-1 w-56 overflow-hidden rounded-lg bg-panelalt shadow-xl ring-1 ring-slate-700">
          {options.map((opt) => {
            const active = selected.includes(opt)
            return (
              <label
                key={opt}
                className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm transition hover:bg-slate-700"
              >
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => toggle(opt)}
                  className="h-4 w-4 accent-bull"
                />
                <span className={active ? 'text-white' : 'text-slate-300'}>
                  {opt}
                </span>
              </label>
            )
          })}
        </div>
      )}
    </div>
  )
}
