import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchPreferences, updatePreferences, type InvestingStyle } from '../api'
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

/** Server-side preferences (investing style). Defaults to investor until loaded. */
export function usePreferences() {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: queryKeys.preferences,
    queryFn: fetchPreferences,
    staleTime: Infinity, // only changes through setStyle below
  })

  const mutation = useMutation({
    mutationFn: (style: InvestingStyle) => updatePreferences({ investing_style: style }),
    // Flip the toggle immediately; roll back if the save fails.
    onMutate: async (style) => {
      await qc.cancelQueries({ queryKey: queryKeys.preferences })
      const previous = qc.getQueryData(queryKeys.preferences)
      qc.setQueryData(queryKeys.preferences, { investing_style: style })
      return { previous }
    },
    onError: (_err, _style, ctx) => qc.setQueryData(queryKeys.preferences, ctx?.previous),
    onSuccess: () => {
      SIGNAL_QUERIES.forEach((key) => qc.invalidateQueries({ queryKey: key }))
    },
  })

  return {
    style: query.data?.investing_style ?? 'investor',
    setStyle: mutation.mutate,
    isSaving: mutation.isPending,
    error: mutation.error,
  }
}
