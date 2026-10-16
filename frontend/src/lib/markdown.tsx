import { Fragment, type ReactNode } from 'react'

/** **bold** and *italic* spans within one line. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/g).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4)
      return (
        <strong key={i} className="font-semibold text-ink">
          {part.slice(2, -2)}
        </strong>
      )
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2)
      return (
        <em key={i} className="text-subtle">
          {part.slice(1, -1)}
        </em>
      )
    return <Fragment key={i}>{part}</Fragment>
  })
}

/**
 * Minimal, safe renderer for the assistant's replies: paragraphs, **bold**,
 * and "-" / "*" bullet lists (two-space indent nests). It builds React nodes
 * from text — never HTML — so model output can't inject markup.
 */
export function renderMarkdown(source: string): ReactNode {
  const blocks: ReactNode[] = []
  let para: string[] = []
  let items: { depth: number; text: string }[] = []

  const flushPara = () => {
    if (para.length) {
      blocks.push(
        <p key={blocks.length}>
          {para.map((line, i) => (
            <Fragment key={i}>
              {i > 0 && <br />}
              {inline(line)}
            </Fragment>
          ))}
        </p>,
      )
      para = []
    }
  }
  const flushList = () => {
    if (items.length) {
      blocks.push(
        <ul key={blocks.length} className="space-y-0.5">
          {items.map((it, i) => (
            <li
              key={i}
              className="flex gap-1.5"
              style={{ paddingLeft: `${it.depth * 0.9}rem` }}
            >
              <span className="text-subtle" aria-hidden>
                •
              </span>
              <span>{inline(it.text)}</span>
            </li>
          ))}
        </ul>,
      )
      items = []
    }
  }

  for (const raw of source.replace(/\r/g, '').split('\n')) {
    const bullet = raw.match(/^(\s*)[-*]\s+(.*)$/)
    if (bullet) {
      flushPara()
      items.push({ depth: Math.floor(bullet[1].length / 2), text: bullet[2].trim() })
    } else if (raw.trim() === '') {
      flushPara()
      flushList()
    } else {
      flushList()
      para.push(raw.trim())
    }
  }
  flushPara()
  flushList()
  return <div className="space-y-2">{blocks}</div>
}
