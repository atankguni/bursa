import { useQuery } from '@tanstack/react-query'
import { fetchFundamentals } from '../api'
import { queryKeys } from './keys'

/** Yearly fundamentals for a ticker (fetched on demand + cached). */
export function useFundamentals(ticker: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.fundamentals(ticker),
    queryFn: () => fetchFundamentals(ticker),
    enabled,
  })
}
