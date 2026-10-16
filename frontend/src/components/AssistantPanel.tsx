import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Loader2, RotateCcw, SendHorizontal, Sparkles, X } from 'lucide-react'
import { askAssistant, type ChatTurn } from '../api'
import { queryKeys, useAssistantStatus } from '../hooks'
import { renderMarkdown } from '../lib/markdown'

interface Message extends ChatTurn {
  tools?: string[]
  error?: boolean
}

const SUGGESTIONS = [
  'Which stocks have the strongest signal right now?',
  'Explain BBCA’s signal',
  'Saham bank mana yang PBV-nya di bawah 1?',
  'How is the market doing today?',
]

const PAGE_CONTEXT: Record<string, string> = {
  '/': 'the Home page (index constituents with prices and signals)',
  '/watchlist': 'the Watchlist page',
  '/portfolio': 'the Portfolio page',
  '/screener': 'the Screener page',
  '/market': 'the Market overview page',
  '/browse': 'the Browse IDX catalog page',
  '/alerts': 'the Alerts page',
}

const errorText = (err: unknown) =>
  isAxiosError(err)
    ? ((err.response?.data?.detail as string | undefined) ??
      (err.code === 'ECONNABORTED'
        ? 'The assistant took too long — try again.'
        : err.message))
    : 'Something went wrong.'

/** Navbar button + side drawer chat with the AI assistant (read-only over app data). */
export default function AssistantPanel() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const { pathname } = useLocation()
  const qc = useQueryClient()
  const status = useAssistantStatus(open)

  const ask = useMutation({
    mutationFn: (history: ChatTurn[]) => askAssistant(history, PAGE_CONTEXT[pathname]),
    onSuccess: (r) => {
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: r.reply, tools: r.tools_used },
      ])
      qc.setQueryData(queryKeys.assistantStatus, (s: typeof status.data) =>
        s ? { ...s, remaining_today: r.remaining_today } : s,
      )
    },
    onError: (err) =>
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: errorText(err), error: true },
      ]),
  })

  const send = (text: string) => {
    const question = text.trim()
    if (!question || ask.isPending) return
    const next: Message[] = [...messages, { role: 'user', content: question }]
    setMessages(next)
    setDraft('')
    // Only real conversation turns go to the model, never our error bubbles.
    ask.mutate(
      next.filter((m) => !m.error).map(({ role, content }) => ({ role, content })),
    )
  }

  // Keep the newest message in view; focus the input when opened.
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages, ask.isPending])
  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const s = status.data
  const notConfigured = s && !s.configured
  const outOfQuota = s?.configured && s.remaining_today <= 0
  const disabled = ask.isPending || !!notConfigured || !!outOfQuota

  return (
    <>
      <button
        onClick={() => setOpen((v) => !v)}
        title="Ask the assistant"
        aria-label="Ask the assistant"
        aria-expanded={open}
        className={`rounded p-2 ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink ${
          open ? 'bg-panelalt text-ink' : 'text-muted'
        }`}
      >
        <Sparkles size={15} />
      </button>

      {open &&
        createPortal(
          <aside
            role="dialog"
            aria-label="AI assistant"
            className="fixed inset-y-0 right-0 z-40 flex w-full max-w-md animate-fade-in flex-col border-l border-line bg-panel shadow-pop"
          >
            {/* Header */}
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div className="flex items-center gap-2.5">
                <div className="rounded-md bg-gradient-to-br from-bull to-emerald-600 p-1.5 text-white shadow-card">
                  <Sparkles size={14} strokeWidth={2.5} />
                </div>
                <div className="leading-tight">
                  <h2 className="text-sm font-semibold tracking-tight">Assistant</h2>
                  <p className="text-[10px] text-subtle">
                    {s?.configured
                      ? `${s.remaining_today}/${s.daily_limit} questions left today`
                      : 'Answers from Bursa’s data'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {messages.length > 0 && (
                  <button
                    onClick={() => setMessages([])}
                    disabled={ask.isPending}
                    title="New conversation"
                    aria-label="New conversation"
                    className="rounded p-1.5 text-muted transition hover:bg-panelalt hover:text-ink disabled:opacity-40"
                  >
                    <RotateCcw size={15} />
                  </button>
                )}
                <button
                  onClick={() => setOpen(false)}
                  aria-label="Close assistant"
                  className="rounded p-1.5 text-muted transition hover:bg-panelalt hover:text-ink"
                >
                  <X size={17} />
                </button>
              </div>
            </div>

            {/* Conversation */}
            <div
              ref={listRef}
              className="flex-1 space-y-3 overflow-y-auto px-4 py-4 text-xs"
            >
              {notConfigured && (
                <div className="rounded-md bg-bear/10 px-3 py-2 text-bear ring-1 ring-bear/20">
                  The assistant isn’t set up. Add{' '}
                  <code>{s.setup_hint || 'an API key'}</code> to <code>backend/.env</code>{' '}
                  and restart the backend.
                </div>
              )}
              {messages.length === 0 && !notConfigured && (
                <div className="space-y-3">
                  <p className="text-muted">
                    Ask about stocks, signals, the screener or the market. Answers use
                    Bursa’s live data.
                  </p>
                  <div className="flex flex-col items-start gap-1.5">
                    {SUGGESTIONS.map((q) => (
                      <button
                        key={q}
                        onClick={() => send(q)}
                        disabled={disabled}
                        className="rounded-md bg-panelalt/70 px-2.5 py-1.5 text-left text-muted ring-1 ring-line transition hover:bg-active hover:text-ink disabled:opacity-50"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m, i) =>
                m.role === 'user' ? (
                  <div key={i} className="flex justify-end">
                    <div className="max-w-[85%] whitespace-pre-wrap rounded-md bg-active px-3 py-2 text-ink">
                      {m.content}
                    </div>
                  </div>
                ) : (
                  <div key={i} className="max-w-[95%] space-y-1">
                    <div
                      className={`rounded-md px-3 py-2 leading-relaxed ring-1 ${
                        m.error
                          ? 'bg-bear/10 text-bear ring-bear/20'
                          : 'bg-panelalt/50 text-muted ring-line'
                      }`}
                    >
                      {m.error ? m.content : renderMarkdown(m.content)}
                    </div>
                    {m.tools && m.tools.length > 0 && (
                      <p className="px-1 text-[10px] text-subtle">
                        Looked up: {[...new Set(m.tools)].join(', ').replace(/_/g, ' ')}
                      </p>
                    )}
                  </div>
                ),
              )}

              {ask.isPending && (
                <div
                  className="flex items-center gap-2 px-1 text-subtle"
                  aria-live="polite"
                >
                  <Loader2 size={13} className="animate-spin" /> Looking that up…
                </div>
              )}
            </div>

            {/* Composer */}
            <form
              onSubmit={(e) => {
                e.preventDefault()
                send(draft)
              }}
              className="border-t border-line px-3 py-3"
            >
              <div className="flex items-end gap-2 rounded-md bg-panelalt/70 px-2.5 py-2 ring-1 ring-line-strong focus-within:ring-bull">
                <textarea
                  ref={inputRef}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      send(draft)
                    }
                  }}
                  rows={2}
                  maxLength={4000}
                  placeholder={
                    outOfQuota ? 'Daily limit reached' : 'Ask anything about Bursa…'
                  }
                  disabled={!!notConfigured || !!outOfQuota}
                  aria-label="Your question"
                  className="max-h-32 flex-1 resize-none bg-transparent text-xs text-ink outline-none placeholder:text-subtle"
                />
                <button
                  type="submit"
                  disabled={disabled || !draft.trim()}
                  aria-label="Send"
                  className="rounded p-1.5 text-bull transition hover:bg-bull/10 disabled:text-subtle disabled:opacity-50"
                >
                  <SendHorizontal size={16} />
                </button>
              </div>
              <p className="mt-1.5 px-1 text-[10px] text-subtle">
                AI can make mistakes · not financial advice ·{' '}
                {s?.personal_data
                  ? 'can read your portfolio'
                  : 'portfolio & watchlist not shared'}
              </p>
            </form>
          </aside>,
          document.body,
        )}
    </>
  )
}
