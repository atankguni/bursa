import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

const html = (source: string) => renderToStaticMarkup(renderMarkdown(source))

describe('renderMarkdown (assistant replies)', () => {
  it('never turns model output into markup', () => {
    const out = html('<img src=x onerror="alert(1)"> **<script>alert(2)</script>**')
    expect(out).not.toContain('<img')
    expect(out).not.toContain('<script')
    expect(out).toContain('&lt;img')
    expect(out).toContain('&lt;script&gt;')
  })

  it('renders bold, italic and paragraphs', () => {
    const out = html('A **strong** and *soft* point.\nSame paragraph.\n\nNext one.')
    expect(out).toContain('<strong class="font-semibold text-ink">strong</strong>')
    expect(out).toContain('<em class="text-subtle">soft</em>')
    expect(out.match(/<p>/g)).toHaveLength(2)
    expect(out).toContain('<br/>')
  })

  it('renders bullet lists, nested by two-space indents', () => {
    const out = html('- one\n  * nested\n- two')
    expect(out.match(/<li /g)).toHaveLength(3)
    expect(out).toContain('padding-left:0.9rem')
  })

  it('leaves a lone asterisk alone', () => {
    expect(html('2 * 3 = 6')).toContain('2 * 3 = 6')
  })
})
