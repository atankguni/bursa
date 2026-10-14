import { useQuery } from '@tanstack/react-query'
import { fetchRecommendation } from '../api'
import { queryKeys } from './keys'

/** Buy-signal score for a ticker (relative to the tracked universe). */
export function useRecommendation(ticker: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.recommendation(ticker),
    queryFn: () => fetchRecommendation(ticker),
    enabled,
  })
}
