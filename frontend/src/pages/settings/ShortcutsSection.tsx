/** Shortcuts: the keys Bursa listens for (a reference; nothing to change). */
import { Rows } from './controls'

const isMac =
  typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
const mod = isMac ? '⌘' : 'Ctrl'

const SHORTCUTS: { keys: string[][]; what: string }[] = [
  { keys: [[mod, 'K'], ['/']], what: 'Search stocks' },
  { keys: [['↑'], ['↓']], what: 'Move through the search results' },
  { keys: [['Enter']], what: 'Open the highlighted result' },
  { keys: [[',']], what: 'Open Settings' },
  { keys: [['Esc']], what: 'Close a dialog, menu or search' },
  { keys: [['Enter']], what: 'Save a field you are typing in (fees, limits, names)' },
]

function Key({ children }: { children: string }) {
  return (
    <kbd className="inline-flex min-w-6 items-center justify-center rounded-sm bg-panel px-1.5 py-0.5 font-sans text-2xs font-medium text-ink shadow-card ring-1 ring-line-strong">
      {children}
    </kbd>
  )
}

export default function ShortcutsSection() {
  return (
    <div className="space-y-3">
      <Rows>
        {SHORTCUTS.map(({ keys, what }) => (
          <div
            key={what}
            className="flex items-center justify-between gap-4 px-3.5 py-2.5"
          >
            <span className="text-xs text-ink">{what}</span>
            <span className="flex shrink-0 items-center gap-1.5 text-2xs text-subtle">
              {keys.map((combo, i) => (
                <span key={combo.join('+')} className="flex items-center gap-1">
                  {i > 0 && <span className="mr-0.5">or</span>}
                  {combo.map((k) => (
                    <Key key={k}>{k}</Key>
                  ))}
                </span>
              ))}
            </span>
          </div>
        ))}
      </Rows>
      <p className="text-2xs text-subtle">
        On phones, the Back button or gesture closes the dialog on top instead of leaving
        the page.
      </p>
    </div>
  )
}
