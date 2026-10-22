import { useMutation, useQuery } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Send } from 'lucide-react'
import { fetchNotificationStatus, sendTestNotification } from '../api'
import { errorDetail } from '../api/client'

/** Telegram delivery status for alerts, with a test button and setup steps. */
export default function NotificationsCard() {
  const status = useQuery({
    queryKey: ['alerts', 'notifications'],
    queryFn: fetchNotificationStatus,
  })
  const test = useMutation({ mutationFn: sendTestNotification })
  const on = status.data?.telegram
  const error =
    test.error && isAxiosError(test.error)
      ? (errorDetail(test.error) ?? test.error.message)
      : null

  return (
    <div className="surface p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs">
          <Send size={14} className="text-muted" aria-hidden />
          <span className="font-medium text-ink">Telegram</span>
          <span className={on ? 'text-bull' : 'text-subtle'}>
            {on
              ? '● Connected: triggered alerts are also sent to Telegram'
              : '○ Not set up: alerts show in the app only'}
          </span>
        </div>
        {on && (
          <button
            onClick={() => test.mutate()}
            disabled={test.isPending}
            className="rounded px-2.5 py-1 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50"
          >
            {test.isPending ? 'Sending…' : 'Send test'}
          </button>
        )}
      </div>
      {test.isSuccess && (
        <p className="mt-1.5 text-[11px] text-bull">Test sent: check Telegram.</p>
      )}
      {error && <p className="mt-1.5 text-[11px] text-bear">{error}</p>}
      {status.data && !on && (
        <ol className="mt-2 list-decimal space-y-0.5 pl-5 text-[11px] text-subtle">
          <li>
            In Telegram, message <b>@BotFather</b>, send <code>/newbot</code>, and copy
            the token.
          </li>
          <li>Open a chat with your new bot and send it any message.</li>
          <li>
            Visit <code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code> and
            copy the <code>chat.id</code> number.
          </li>
          <li>
            Add <code>TELEGRAM_BOT_TOKEN=…</code> and <code>TELEGRAM_CHAT_ID=…</code> to{' '}
            <code>backend/.env</code>, then restart the backend.
          </li>
        </ol>
      )}
    </div>
  )
}
