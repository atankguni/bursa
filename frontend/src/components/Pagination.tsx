import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'

/** Page numbers to show: first, last, and a window around the current page. */
function pageItems(page: number, pageCount: number): (number | 'gap')[] {
  const wanted = new Set([0, pageCount - 1, page - 1, page, page + 1])
  const pages = [...wanted].filter((p) => p >= 0 && p < pageCount).sort((a, b) => a - b)
  const out: (number | 'gap')[] = []
  pages.forEach((p, i) => {
    const prev = pages[i - 1]
    if (prev !== undefined && p - prev > 1) out.push('gap')
    out.push(p)
  })
  return out
}

const btn =
  'inline-flex h-7 min-w-7 items-center justify-center rounded px-2 text-xs tabular-nums transition disabled:pointer-events-none disabled:opacity-40'

/** Numbered pager. `page` is 0-based; renders nothing when everything fits on one page. */
export default function Pagination({
  page,
  pageCount,
  onChange,
}: {
  page: number
  pageCount: number
  onChange: (page: number) => void
}) {
  if (pageCount <= 1) return null
  const go = (p: number) => onChange(Math.min(Math.max(p, 0), pageCount - 1))
  const icon = `${btn} text-muted hover:bg-panelalt hover:text-ink`

  return (
    <nav aria-label="Pagination" className="flex items-center gap-1">
      <button
        onClick={() => go(0)}
        disabled={page === 0}
        className={icon}
        aria-label="First page"
      >
        <ChevronsLeft size={14} />
      </button>
      <button
        onClick={() => go(page - 1)}
        disabled={page === 0}
        className={icon}
        aria-label="Previous page"
      >
        <ChevronLeft size={14} />
      </button>
      {pageItems(page, pageCount).map((p, i) =>
        p === 'gap' ? (
          <span key={`gap-${i}`} className="px-1 text-xs text-subtle" aria-hidden>
            …
          </span>
        ) : (
          <button
            key={p}
            onClick={() => go(p)}
            aria-current={p === page ? 'page' : undefined}
            aria-label={`Page ${p + 1}`}
            className={`${btn} ${
              p === page
                ? 'bg-panel font-semibold text-ink shadow-card ring-1 ring-line-strong'
                : 'text-muted hover:bg-panelalt hover:text-ink'
            }`}
          >
            {p + 1}
          </button>
        ),
      )}
      <button
        onClick={() => go(page + 1)}
        disabled={page >= pageCount - 1}
        className={icon}
        aria-label="Next page"
      >
        <ChevronRight size={14} />
      </button>
      <button
        onClick={() => go(pageCount - 1)}
        disabled={page >= pageCount - 1}
        className={icon}
        aria-label="Last page"
      >
        <ChevronsRight size={14} />
      </button>
    </nav>
  )
}
