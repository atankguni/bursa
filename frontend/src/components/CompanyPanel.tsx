import { AlertCircle, ExternalLink } from 'lucide-react'
import type { Company } from '../api'

export default function CompanyPanel({
  data,
  isLoading,
  isError,
  section = 'overview',
}: {
  data?: Company | undefined
  isLoading: boolean
  isError?: boolean
  section?: 'overview' | 'board'
}) {
  if (isLoading) {
    return (
      <div className="flex h-[300px] items-center justify-center text-muted">
        Loading company info…
      </div>
    )
  }
  if (isError || !data) {
    return (
      <div className="flex h-[300px] flex-col items-center justify-center gap-2 text-muted">
        <AlertCircle size={20} />
        <span className="text-sm">No company information available.</span>
      </div>
    )
  }

  const facts = [
    { label: 'Sector', value: data.sector },
    { label: 'Industry', value: data.industry },
    { label: 'Employees', value: data.employees?.toLocaleString('en-US') },
    { label: 'Country', value: data.country },
    { label: 'City', value: data.city },
    { label: 'Address', value: data.address },
    { label: 'Phone', value: data.phone },
  ].filter((f) => f.value)

  return (
    <div className="space-y-4">
      {section === 'overview' && (
        <>
          {data.description && (
            <div className="surface p-4">
              <div className="mb-2 text-[10px] uppercase tracking-wider text-muted">
                About {data.name}
              </div>
              <p className="text-xs leading-relaxed text-muted">{data.description}</p>
            </div>
          )}

          {facts.length > 0 && (
            <div className="surface p-4">
              <div className="mb-3 text-[10px] uppercase tracking-wider text-muted">
                Details
              </div>
              <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
                {facts.map((f) => (
                  <div
                    key={f.label}
                    className="flex items-baseline justify-between gap-3 text-xs"
                  >
                    <dt className="text-subtle">{f.label}</dt>
                    <dd className="text-right text-ink">{f.value}</dd>
                  </div>
                ))}
              </dl>
              {data.website && (
                <a
                  href={data.website}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-accent transition hover:opacity-80"
                >
                  <ExternalLink size={12} /> {data.website.replace(/^https?:\/\//, '')}
                </a>
              )}
            </div>
          )}
        </>
      )}

      {section === 'board' && data.officers.length > 0 && (
        <div className="surface p-4">
          <div className="mb-3 text-[10px] uppercase tracking-wider text-muted">
            Board &amp; management
          </div>
          <ul className="divide-y divide-line">
            {data.officers.map((o, i) => (
              <li
                key={`${o.name}-${i}`}
                className="flex items-baseline justify-between gap-3 py-2 text-xs"
              >
                <span className="font-medium text-ink">{o.name}</span>
                <span className="text-right text-subtle">{o.title}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {section === 'board' && data.officers.length === 0 && (
        <div className="py-10 text-center text-sm text-muted">
          No board information available.
        </div>
      )}
    </div>
  )
}
