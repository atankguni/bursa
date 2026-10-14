import { useQuery } from '@tanstack/react-query'
import { fetchPortfolio, fetchPortfolioHistory, fetchTransactions } from '../api'
import { useSettings } from '../lib/settings'
import { queryKeys } from './keys'

/** Portfolio holdings + totals, polled per the auto-refresh setting. */
export function usePortfolio() {
  const { settings } = useSettings()
  return useQuery({
    queryKey: queryKeys.portfolio,
    queryFn: fetchPortfolio,
    refetchInterval: settings.autoRefresh ? settings.refreshSeconds * 1000 : false,
  })
}

export function useTransactions() {
  return useQuery({
    queryKey: queryKeys.transactions,
    queryFn: fetchTransactions,
  })
}

export function usePortfolioHistory() {
  return useQuery({
    queryKey: queryKeys.portfolioHistory,
    queryFn: fetchPortfolioHistory,
  })
}
