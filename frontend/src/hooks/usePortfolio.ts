import { useQuery } from '@tanstack/react-query'
import {
  fetchDividendCalendar,
  fetchPortfolio,
  fetchPortfolioHistory,
  fetchPortfolioRisk,
  fetchTransactions,
} from '../api'
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

/** Concentration, sectors, beta vs IHSG, stress test and drawdown (percentages only). */
export function usePortfolioRisk(enabled = true) {
  return useQuery({
    queryKey: queryKeys.portfolioRisk,
    queryFn: fetchPortfolioRisk,
    enabled,
  })
}

/** Expected (projected) dividends for holdings + watchlist over the next 6 months. */
export function useDividendCalendar() {
  return useQuery({
    queryKey: queryKeys.dividendCalendar,
    queryFn: () => fetchDividendCalendar(),
  })
}
