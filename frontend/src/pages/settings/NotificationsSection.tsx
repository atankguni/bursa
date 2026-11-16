/** Notifications: the daily summary, alert emails and quiet hours (your account). */
import { useMutation, useQuery } from '@tanstack/react-query'
import { fetchAuthOptions, sendDigestPreview } from '../../api'
import { errorDetail } from '../../api/client'
import { usePreferences } from '../../hooks'
import { ListRow, Rows, Switch } from './controls'

/** The summary email after the close (needs email set up on the server). */
function DigestSettings({ emailReady }: { emailReady: boolean }) {
  const { dailyDigest, setDailyDigest } = usePreferences()
  const preview = useMutation({ mutationFn: sendDigestPreview })
  const detail = errorDetail(preview.error)
  return (
    <Rows>
      <ListRow
        label="Daily summary email"
        hint={
          emailReady
            ? 'After the close on trading days: your portfolio’s day, big moves, signal changes and dividends coming up.'
            : 'Needs email to be set up on the server (an admin can do that).'
        }
      >
        <Switch
          checked={dailyDigest}
          onChange={setDailyDigest}
          label="Daily summary email"
          disabled={!emailReady}
        />
      </ListRow>
      {emailReady && (
        <ListRow
          label="Preview"
          hint={
            preview.isSuccess
              ? 'Sent: check your inbox.'
              : (detail ?? 'Email today’s summary to yourself now.')
          }
        >
          <button
            onClick={() => preview.mutate()}
            disabled={preview.isPending}
            className="rounded-sm px-2.5 py-1 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50"
          >
            {preview.isPending ? 'Sending…' : 'Send now'}
          </button>
        </ListRow>
      )}
    </Rows>
  )
}

const DEFAULT_QUIET = { start: '22:00', end: '07:00' }

function AlertEmailSettings({ emailReady }: { emailReady: boolean }) {
  const { alertEmails, setAlertEmails, quietHours, setQuietHours } = usePreferences()
  const time = (key: 'start' | 'end', label: string) => (
    <input
      type="time"
      aria-label={label}
      value={quietHours?.[key] ?? ''}
      disabled={!quietHours}
      onChange={(e) =>
        quietHours &&
        e.target.value &&
        setQuietHours({ ...quietHours, [key]: e.target.value })
      }
      className="input input-sm w-auto tabular-nums disabled:opacity-40"
    />
  )
  return (
    <Rows>
      <ListRow
        label="Alert emails"
        hint={
          emailReady
            ? 'Email me when one of my alerts triggers (they always show on the Alerts page).'
            : 'Needs email to be set up on the server (an admin can do that).'
        }
      >
        <Switch
          checked={alertEmails}
          onChange={setAlertEmails}
          label="Alert emails"
          disabled={!emailReady}
        />
      </ListRow>
      <ListRow
        label="Quiet hours"
        hint="No alert emails in this window (Jakarta time); what triggers then comes in one email when it ends. Alerts older than a day aren't emailed."
      >
        <Switch
          checked={quietHours !== null}
          onChange={(on) => setQuietHours(on ? DEFAULT_QUIET : null)}
          label="Quiet hours"
        />
      </ListRow>
      {quietHours && (
        <ListRow label="From – to">
          <span className="flex items-center gap-1.5 text-xs text-muted">
            {time('start', 'Quiet from')} – {time('end', 'Quiet until')}
          </span>
        </ListRow>
      )}
    </Rows>
  )
}

export default function NotificationsSection() {
  const { data: options } = useQuery({
    queryKey: ['auth', 'options'],
    queryFn: fetchAuthOptions,
  })
  const emailReady = options?.password_reset_by_email ?? false // email is set up
  return (
    <div className="space-y-5">
      <DigestSettings emailReady={emailReady} />
      <AlertEmailSettings emailReady={emailReady} />
    </div>
  )
}
