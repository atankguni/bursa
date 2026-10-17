import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchPreferences, updatePreferences, type Preferences } from '../api'
import { queryKeys } from './keys'

// Everything that shows a signal / rating is re-scored when the style changes.
const SIGNAL_QUERIES = [
  ['stocks'],
  ['stock'],
  ['watchlist'],
  ['screener'],
  ['recommendation'],
  ['market'],
  ['alerts'],
] as const

/** Server-side preferences. Defaults (investor, no personal data) until loaded. */
export function usePreferences() {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: queryKeys.preferences,
    queryFn: fetchPreferences,
    staleTime: Infinity, // only changes through the mutation below
  })

  const mutation = useMutation({
    mutationFn: (patch: Partial<Preferences>) => updatePreferences(patch),
    // Apply immediately (merged, so one setting never resets another); roll back on error.
    onMutate: async (patch) => {
      await qc.cancelQueries({ queryKey: queryKeys.preferences })
      const previous = qc.getQueryData<Preferences>(queryKeys.preferences)
      if (previous) qc.setQueryData(queryKeys.preferences, { ...previous, ...patch })
      return { previous }
    },
    onError: (_err, _patch, ctx) => qc.setQueryData(queryKeys.preferences, ctx?.previous),
    onSuccess: (saved, patch) => {
      qc.setQueryData(queryKeys.preferences, saved)
      if (patch.investing_style !== undefined) {
        SIGNAL_QUERIES.forEach((key) => qc.invalidateQueries({ queryKey: key }))
      }
      if (patch.assistant_personal_data !== undefined) {
        qc.invalidateQueries({ queryKey: queryKeys.assistantStatus })
      }
    },
  })

  return {
    style: query.data?.investing_style ?? 'investor',
    personalData: query.data?.assistant_personal_data ?? false,
    setStyle: (investing_style: Preferences['investing_style']) =>
      mutation.mutate({ investing_style }),
    setPersonalData: (assistant_personal_data: boolean) =>
      mutation.mutate({ assistant_personal_data }),
    /** Loaded from the server (before that, the values above are defaults). */
    loaded: query.isSuccess,
    alertsSeenAt: query.data?.alerts_seen_at ?? null,
    /** Alerts up to this event time were seen (the server never moves it back). */
    markAlertsSeen: (alerts_seen_at: string) => mutation.mutate({ alerts_seen_at }),
    isSaving: mutation.isPending,
    error: mutation.error,
  }
}
