import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { GLOSSARY, GLOSSARY_GROUPS, type GlossaryEntry } from '../lib/glossary'

/** Every explanation in one place, linked from each "?" popover. */
export default function Glossary() {
  const { hash } = useLocation()
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: 'center' })
  }, [hash])

  return (
    <main className="page max-w-3xl">
      <h2 className="page-title">What the numbers mean</h2>
      <p className="page-sub mb-6">
        Plain-language explanations of what Bursa shows. None of it is advice to buy or
        sell.
      </p>
      <div className="space-y-5">
        {GLOSSARY_GROUPS.map((g) => (
          <section key={g.title}>
            <h3 className="section-title mb-2">{g.title}</h3>
            <dl className="surface divide-y divide-line">
              {g.ids.map((id) => {
                const e: GlossaryEntry = GLOSSARY[id]
                return (
                  <div
                    key={id}
                    id={id}
                    className={`scroll-mt-24 px-4 py-3 text-xs ${
                      hash === `#${id}` ? 'bg-panelalt' : ''
                    }`}
                  >
                    <dt className="font-semibold text-ink">{e.term}</dt>
                    <dd className="mt-1 space-y-1 text-muted">
                      <p>{e.short}</p>
                      {e.example && <p className="text-subtle">{e.example}</p>}
                      {e.read && <p>{e.read}</p>}
                    </dd>
                  </div>
                )
              })}
            </dl>
          </section>
        ))}
      </div>
    </main>
  )
}
