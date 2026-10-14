import { useQuery } from '@tanstack/react-query'
import { fetchCompany, fetchDividends, fetchValuation } from '../api'
import { queryKeys } from './keys'

/** Where the stock's PBV/RoE sit within its own history. */
export function useValuation(ticker: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.valuation(ticker),
    queryFn: () => fetchValuation(ticker),
    enabled,
  })
}

/** Dividend history + trailing yield. */
export function useDividends(ticker: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.dividends(ticker),
    queryFn: () => fetchDividends(ticker),
    enabled,
  })
}

/** Company profile + board/management. */
export function useCompany(ticker: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.company(ticker),
    queryFn: () => fetchCompany(ticker),
    enabled,
  })
}
