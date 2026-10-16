import type { ReactNode } from 'react'

export type SortDir = 'asc' | 'desc'
export interface SortState<K extends string> {
  key: K
  dir: SortDir
}

/** Table header cell that sorts by `sortKey`; click again to flip direction. */
export default function SortHeader<K extends string>({
  sortKey,
  sort,
  onSort,
  align = 'left',
  className = '',
  children,
}: {
  sortKey: K
  sort: SortState<K>
  onSort: (key: K) => void
  align?: 'left' | 'right'
  className?: string
  children: ReactNode
}) {
  const active = sort.key === sortKey
  return (
    <th
      scope="col"
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
      className={`px-4 py-2.5 ${align === 'right' ? 'text-right' : ''} ${className}`}
    >
      <button
        onClick={() => onSort(sortKey)}
        className={`inline-flex items-center gap-1 uppercase tracking-wider transition hover:text-ink ${
          active ? 'text-ink' : ''
        }`}
      >
        {children}
        <span className="text-[8px]" aria-hidden>
          {active ? (sort.dir === 'asc' ? '▲' : '▼') : '↕'}
        </span>
      </button>
    </th>
  )
}
