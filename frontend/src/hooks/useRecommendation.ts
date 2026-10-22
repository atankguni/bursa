import { useQuery } from '@tanstack/react-query'
import { fetchRecommendation, fetchTrackRecord } from '../api'
import { queryKeys } from './keys'

/** Buy-signal score for a ticker (relative to the tracked universe). */
export function useRecommendation(ticker: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.recommendation(ticker),
    queryFn: () => fetchRecommendation(ticker),
    enabled,
  })
}

/** Past ratings vs. what happened next; changes at most daily. */
export function useTrackRecord(enabled = true) {
  return useQuery({
    queryKey: queryKeys.trackRecord,
    queryFn: fetchTrackRecord,
    enabled,
    staleTime: 60 * 60 * 1000,
  })
}
