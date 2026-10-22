import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import {
  ArrowLeft,
  History,
  Loader2,
  SendHorizontal,
  SquarePen,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import {
  askAssistant,
  deleteAllChats,
  deleteChat,
  fetchChat,
  type ChatDetail,
  type ChatSummary,
  type ChatTurn,
} from '../api'
import { queryKeys, useAssistantChats, useAssistantStatus } from '../hooks'
import { fmtShortDateTime, parseServerTime } from '../lib/format'
import { renderMarkdown } from '../lib/markdown'
import { errorDetail } from '../api/client'

interface Message extends ChatTurn {
  tools?: string[] | undefined
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

// The model sees only the recent part of a long chat (the API takes 40 turns).
const MAX_TURNS = 40

const iconBtn =
  'rounded p-1.5 text-muted transition hover:bg-panelalt hover:text-ink disabled:opacity-40'

const toMessages = (chat: ChatDetail): Message[] =>
  chat.messages.map((m) => ({
    role: m.role,
    content: m.content,
    tools: m.tools_used ?? undefined,
  }))

const dayStart = (d: Date) =>
  new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()

/** Today / Yesterday / Earlier, by the chat's last message (local time). */
function groupChats(chats: ChatSummary[]) {
  const today = dayStart(new Date())
  type Group = { label: string; chats: ChatSummary[] }
  const groups: [Group, Group, Group] = [
    { label: 'Today', chats: [] },
    { label: 'Yesterday', chats: [] },
    { label: 'Earlier', chats: [] },
  ]
  for (const c of chats) {
    const t = dayStart(parseServerTime(c.updated_at) ?? new Date())
    groups[t >= today ? 0 : t >= today - 86_400_000 ? 1 : 2].chats.push(c)
  }
  return groups.filter((g) => g.chats.length > 0)
}

const errorText = (err: unknown) =>
  isAxiosError(err)
    ? (errorDetail(err) ??
      (err.code === 'ECONNABORTED'
        ? 'The assistant took too long — try again.'
        : err.message))
    : 'Something went wrong.'

/** Navbar button + side drawer chat with the AI assistant (read-only over app data). */
export default function AssistantPanel() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  // The saved chat being continued (null: a new one, created by the first answer).
  const [chatId, setChatId] = useState<number | null>(null)
  // Last message time of a chat opened from history: older answers may be outdated.
  const [resumedFrom, setResumedFrom] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const resumed = useRef(false)
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const { pathname } = useLocation()
  const qc = useQueryClient()
  const status = useAssistantStatus(open)
  const saving = !!status.data?.save_chats
  const chats = useAssistantChats(open && saving)

  const ask = useMutation({
    mutationFn: (history: ChatTurn[]) =>
      askAssistant(history, PAGE_CONTEXT[pathname], chatId),
    onSuccess: (r) => {
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: r.reply, tools: r.tools_used },
      ])
      setChatId(r.chat_id)
      qc.setQueryData(queryKeys.assistantStatus, (s: typeof status.data) =>
        s ? { ...s, remaining_today: r.remaining_today } : s,
      )
      if (r.chat_id != null)
        void qc.invalidateQueries({ queryKey: queryKeys.assistantChats })
    },
    onError: (err) =>
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: errorText(err), error: true },
      ]),
  })

  const openChat = useMutation({
    mutationFn: fetchChat,
    onSuccess: (chat) => {
      setMessages(toMessages(chat))
      setChatId(chat.id)
      setResumedFrom(chat.updated_at)
      setShowHistory(false)
    },
    // Expired or deleted on another device: refresh the list.
    onError: () => qc.invalidateQueries({ queryKey: queryKeys.assistantChats }),
  })
  const removeChat = useMutation({
    mutationFn: deleteChat,
    onSuccess: (_r, id) => {
      if (id === chatId) newChat()
      void qc.invalidateQueries({ queryKey: queryKeys.assistantChats })
    },
  })
  const removeAll = useMutation({
    mutationFn: deleteAllChats,
    onSuccess: () => {
      newChat()
      qc.setQueryData(queryKeys.assistantChats, [])
    },
  })

  function newChat() {
    setMessages([])
    setChatId(null)
    setResumedFrom(null)
    setShowHistory(false)
    ask.reset()
  }

  // First open: continue the most recent saved chat.
  useEffect(() => {
    if (resumed.current || !chats.data) return
    resumed.current = true
    const latest = chats.data[0]
    if (latest && messages.length === 0 && !ask.isPending) openChat.mutate(latest.id)
  }, [chats.data, messages.length, ask.isPending, openChat])

  const send = (text: string) => {
    const question = text.trim()
    if (!question || ask.isPending) return
    const next: Message[] = [...messages, { role: 'user', content: question }]
    setMessages(next)
    setDraft('')
    // Only real conversation turns go to the model, never our error bubbles,
    // and only the recent part of a long chat.
    ask.mutate(
      next
        .filter((m) => !m.error)
        .map(({ role, content }) => ({ role, content }))
        .slice(-MAX_TURNS),
    )
  }

  const confirmDeleteAll = () => {
    if (window.confirm('Delete all your saved assistant chats?')) removeAll.mutate()
  }
  const resumedDate = parseServerTime(resumedFrom)
  const outdated = resumedDate && dayStart(resumedDate) < dayStart(new Date())

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
                <div className="rounded-md bg-accent p-1.5 text-accent-ink shadow-card">
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
                {saving && (
                  <button
                    onClick={() => setShowHistory((v) => !v)}
                    title="Saved chats"
                    aria-label="Saved chats"
                    aria-pressed={showHistory}
                    className={`${iconBtn} ${showHistory ? 'bg-panelalt text-ink' : ''}`}
                  >
                    <History size={15} />
                  </button>
                )}
                {(messages.length > 0 || showHistory) && (
                  <button
                    onClick={newChat}
                    disabled={ask.isPending}
                    title="New chat"
                    aria-label="New chat"
                    className={iconBtn}
                  >
                    <SquarePen size={15} />
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

            {showHistory && (
              <div className="flex-1 overflow-y-auto px-2 py-3 text-xs">
                <button
                  onClick={() => setShowHistory(false)}
                  className="mb-2 flex items-center gap-1.5 px-2 text-muted hover:text-ink"
                >
                  <ArrowLeft size={13} /> Back to chat
                </button>
                {chats.isPending ? (
                  <p className="px-2 text-subtle">Loading…</p>
                ) : !chats.data?.length ? (
                  <p className="px-2 text-subtle">No saved chats yet.</p>
                ) : (
                  groupChats(chats.data).map((g) => (
                    <div key={g.label} className="mb-3">
                      <h3 className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                        {g.label}
                      </h3>
                      {g.chats.map((c) => (
                        <div
                          key={c.id}
                          className={`group flex items-center gap-1 rounded ${
                            c.id === chatId ? 'bg-panelalt' : 'hover:bg-panelalt/60'
                          }`}
                        >
                          <button
                            onClick={() => openChat.mutate(c.id)}
                            disabled={openChat.isPending || ask.isPending}
                            className="min-w-0 flex-1 px-2 py-1.5 text-left"
                          >
                            <span className="block truncate text-ink">{c.title}</span>
                            <span className="text-[10px] text-subtle">
                              {fmtShortDateTime(c.updated_at)}
                            </span>
                          </button>
                          <button
                            onClick={() => removeChat.mutate(c.id)}
                            disabled={removeChat.isPending}
                            title="Delete chat"
                            aria-label={`Delete chat: ${c.title}`}
                            className={`${iconBtn} mr-1 hover:text-bear`}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      ))}
                    </div>
                  ))
                )}
                <div className="space-y-2 border-t border-line px-2 pt-3 text-[11px] text-subtle">
                  <p>
                    Chats are private to you and deleted {status.data?.chat_days ?? 90}{' '}
                    days after their last message. Turn saving off in Settings →
                    Investing.
                  </p>
                  {(chats.data?.length ?? 0) > 0 && (
                    <button
                      onClick={confirmDeleteAll}
                      disabled={removeAll.isPending}
                      className="text-bear hover:underline disabled:opacity-50"
                    >
                      Delete all chats
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Conversation */}
            <div
              ref={listRef}
              hidden={showHistory}
              className="flex-1 space-y-3 overflow-y-auto px-4 py-4 text-xs"
            >
              {openChat.isPending && (
                <div className="flex items-center gap-2 px-1 text-subtle">
                  <Loader2 size={13} className="animate-spin" /> Opening chat…
                </div>
              )}
              {outdated && messages.length > 0 && (
                <div className="rounded-md bg-amber-500/10 px-3 py-2 text-[11px] text-amber-700 ring-1 ring-amber-500/20 dark:text-amber-400">
                  Continued from {fmtShortDateTime(resumedFrom)}. Prices in earlier
                  answers may be outdated; new questions use fresh data.
                </div>
              )}
              {notConfigured && (
                <div className="rounded-md bg-bear/10 px-3 py-2 text-bear ring-1 ring-bear/20">
                  The assistant isn’t set up. Add{' '}
                  <code>{s.setup_hint || 'an API key'}</code> to <code>backend/.env</code>{' '}
                  and restart the backend.
                </div>
              )}
              {messages.length === 0 && !notConfigured && !openChat.isPending && (
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
              hidden={showHistory}
              onSubmit={(e) => {
                e.preventDefault()
                send(draft)
              }}
              className="border-t border-line px-3 py-3"
            >
              <div className="flex items-end gap-2 rounded-md bg-panelalt/70 px-2.5 py-2 ring-1 ring-line-strong focus-within:ring-accent">
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
                  className="rounded p-1.5 text-accent transition hover:bg-accent/10 disabled:text-subtle disabled:opacity-50"
                >
                  <SendHorizontal size={16} />
                </button>
              </div>
              <p className="mt-1.5 px-1 text-[10px] text-subtle">
                AI can make mistakes · not financial advice ·{' '}
                {s?.personal_data
                  ? 'can read your portfolio'
                  : 'portfolio & watchlist not shared'}{' '}
                · {s?.save_chats ? `chats kept ${s.chat_days} days` : 'chats not saved'}
              </p>
            </form>
          </aside>,
          document.body,
        )}
    </>
  )
}
