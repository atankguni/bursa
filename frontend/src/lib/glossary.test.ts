import { describe, expect, it } from 'vitest'
import { categoryEntry, GLOSSARY, GLOSSARY_GROUPS } from './glossary'

describe('glossary', () => {
  it('lists every entry exactly once on the Glossary page', () => {
    const listed = GLOSSARY_GROUPS.flatMap((g) => g.ids)
    expect([...listed].sort()).toEqual(Object.keys(GLOSSARY).sort())
  })

  it('explains every rating category the API sends', () => {
    for (const name of [
      'Quality',
      'Valuation',
      'Growth',
      'Momentum',
      'Health',
      'Stability',
      'Setup',
    ])
      expect(categoryEntry(name)).not.toBeNull()
    expect(categoryEntry('Unknown')).toBeNull()
    expect(categoryEntry('toString')).toBeNull()
  })
})
