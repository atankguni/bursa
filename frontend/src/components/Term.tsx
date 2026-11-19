import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { CircleHelp } from 'lucide-react'
import { GLOSSARY, type GlossaryId } from '../lib/glossary'

/**
 * A label with a small "?" that opens a plain-language explanation. Tapped, not
 * hovered, so it works on phones; Escape or a tap elsewhere closes it.
 */
export default function Term({ id, children }: { id: GlossaryId; children?: ReactNode }) {
  const entry = GLOSSARY[id]
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLSpanElement>(null)
  const popId = useId()

  useEffect(() => {
    if (!open) return
    const outside = (e: PointerEvent) => {
      if (e.target instanceof Node && !box.current?.contains(e.target)) setOpen(false)
    }
    const escape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  return (
    <span ref={box} className="relative inline-flex items-center gap-0.5">
      {children ?? entry.term}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation() // inside sortable headers and clickable rows
          setOpen((v) => !v)
        }}
        aria-expanded={open}
        aria-controls={popId}
        aria-label={`What is ${entry.term}?`}
        className="rounded-sm p-0.5 text-subtle transition hover:text-ink"
      >
        <CircleHelp size={11} />
      </button>
      {open && (
        <span
          id={popId}
          role="note"
          onClick={(e) => e.stopPropagation()}
          className="absolute top-full left-0 z-30 mt-1 block w-72 max-w-[calc(100vw-2rem)] space-y-1.5 rounded-md bg-panel p-3 text-left text-xs font-normal tracking-normal whitespace-normal normal-case text-muted shadow-pop ring-1 ring-line"
        >
          <span className="block font-semibold text-ink">{entry.term}</span>
          <span className="block">{entry.short}</span>
          {'example' in entry && (
            <span className="block text-subtle">{entry.example}</span>
          )}
          {'read' in entry && <span className="block">{entry.read}</span>}
          <Link
            to={`/glossary#${id}`}
            onClick={() => setOpen(false)}
            className="block text-accent hover:underline"
          >
            All explanations
          </Link>
        </span>
      )}
    </span>
  )
}
