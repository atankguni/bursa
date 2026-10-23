import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { History, MonitorSmartphone } from 'lucide-react'
import {
  errorMessage,
  fetchActivity,
  fetchSessions,
  revokeSession,
  signOutOtherSessions,
} from '../api'
import { fmtShortDateTime, fmtTimeAgo } from '../lib/format'
import { eventLabel, isNotable } from '../lib/securityEvents'

const SESSIONS_KEY = ['auth', 'sessions'] as const
const ACTIVITY_KEY = ['auth', 'activity'] as const

const cardCls = 'rounded-md bg-panelalt/40 p-4 ring-1 ring-line'
const secondaryBtn =
  'rounded px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50'
const smallBtn =
  'rounded px-2 py-1 text-[11px] font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50'

function Heading({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="mb-2 flex items-center gap-2">
      <span className="text-accent">{icon}</span>
      <h3 className="text-sm font-semibold">{title}</h3>
    </div>
  )
}

/** Browsers signed in to your account; sign out one, or all but this one. */
export function SignedInDevices() {
  const qc = useQueryClient()
  const sessions = useQuery({ queryKey: SESSIONS_KEY, queryFn: fetchSessions })
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: SESSIONS_KEY })
    void qc.invalidateQueries({ queryKey: ACTIVITY_KEY })
  }
  const revoke = useMutation({ mutationFn: revokeSession, onSettled: refresh })
  const others = useMutation({ mutationFn: signOutOtherSessions, onSettled: refresh })
  const error = revoke.error ?? others.error
  const otherCount = sessions.data?.filter((s) => !s.current).length ?? 0

  return (
    <section className={cardCls}>
      <Heading icon={<MonitorSmartphone size={16} />} title="Signed-in devices" />
      <div className="space-y-3 text-xs text-muted">
        <p>
          Browsers signed in to your account. Sign out any you don&apos;t recognise, then
          change your password.
        </p>
        {sessions.isPending ? (
          <p className="text-subtle">Loading…</p>
        ) : sessions.isError ? (
          <p className="text-bear">Couldn&apos;t load your devices.</p>
        ) : (
          <ul className="divide-y divide-line rounded ring-1 ring-line">
            {sessions.data.map((s) => (
              <li key={s.id} className="flex items-center gap-3 px-3 py-2">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-ink">
                    {s.device}
                    {s.current && (
                      <span className="ml-2 text-[10px] font-medium text-bull">
                        This browser
                      </span>
                    )}
                  </p>
                  <p className="text-[11px] text-subtle">
                    {s.ip ?? 'Unknown address'} · signed in{' '}
                    {fmtShortDateTime(s.created_at)} · active {fmtTimeAgo(s.last_seen_at)}
                  </p>
                </div>
                {!s.current && (
                  <button
                    onClick={() => revoke.mutate(s.id)}
                    disabled={revoke.isPending}
                    className={smallBtn}
                  >
                    Sign out
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {error && (
          <p className="text-bear">{errorMessage(error, 'Something went wrong.')}</p>
        )}
        {otherCount > 0 && (
          <button
            onClick={() => {
              if (window.confirm(`Sign out your ${otherCount} other device(s)?`)) {
                others.mutate()
              }
            }}
            disabled={others.isPending}
            className={secondaryBtn}
          >
            Sign out all other devices
          </button>
        )}
      </div>
    </section>
  )
}

/** Your latest sign-ins and security changes. */
export function RecentActivity() {
  const activity = useQuery({ queryKey: ACTIVITY_KEY, queryFn: fetchActivity })
  return (
    <section className={cardCls}>
      <Heading icon={<History size={16} />} title="Recent activity" />
      <div className="space-y-3 text-xs text-muted">
        <p>
          Sign-ins and security changes on your account. Highlighted entries are worth a
          look if they weren&apos;t you.
        </p>
        {activity.isPending ? (
          <p className="text-subtle">Loading…</p>
        ) : activity.isError ? (
          <p className="text-bear">Couldn&apos;t load your activity.</p>
        ) : activity.data.length === 0 ? (
          <p className="text-subtle">Nothing yet.</p>
        ) : (
          <ul className="max-h-80 divide-y divide-line overflow-y-auto rounded ring-1 ring-line">
            {activity.data.map((e) => (
              <li key={e.id} className="flex items-baseline gap-3 px-3 py-1.5">
                <span className="w-24 shrink-0 tabular-nums text-subtle">
                  {fmtShortDateTime(e.at)}
                </span>
                <span
                  className={`min-w-0 flex-1 ${
                    isNotable(e)
                      ? 'font-medium text-amber-700 dark:text-amber-400'
                      : 'text-ink'
                  }`}
                >
                  {eventLabel(e)}
                </span>
                <span className="hidden shrink-0 text-[11px] text-subtle sm:inline">
                  {e.device} · {e.ip ?? '—'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
