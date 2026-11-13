/** Grey placeholder bars while data loads (respects reduced motion). */
export function SkeletonRows({
  rows = 6,
  className = '',
}: {
  rows?: number
  className?: string
}) {
  return (
    <div className={`space-y-3 p-4 ${className}`} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-4">
          <div className="skeleton h-4 w-16" />
          <div className="skeleton h-4 flex-1" style={{ opacity: 1 - i * 0.1 }} />
          <div className="skeleton h-4 w-20" />
        </div>
      ))}
    </div>
  )
}

export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div
      className={`surface space-y-3 p-5 ${className}`}
      aria-busy="true"
      aria-label="Loading"
    >
      <div className="skeleton h-3 w-24" />
      <div className="skeleton h-7 w-40" />
      <div className="skeleton h-3 w-32" />
    </div>
  )
}
