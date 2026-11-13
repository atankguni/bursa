import { useQuery } from '@tanstack/react-query'
import {
  fetchDividendCalendar,
  fetchDividendIncome,
  fetchPortfolio,
  fetchPortfolioHistory,
  fetchPortfolioRisk,
  fetchTaxSummary,
  fetchCash,
  fetchNotes,
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

/** Net dividends per month: the last 12 received, the next 6 expected. */
export function useDividendIncome() {
  return useQuery({
    queryKey: queryKeys.dividendIncome,
    queryFn: fetchDividendIncome,
  })
}

/** Expected (projected) dividends for holdings + watchlist over the next 6 months. */
export function useDividendCalendar() {
  return useQuery({
    queryKey: queryKeys.dividendCalendar,
    queryFn: () => fetchDividendCalendar(),
  })
}

/** A year's figures for the tax return (SPT): holdings on 31 December, sales, dividends. */
export function useTaxSummary(year: number) {
  return useQuery({
    queryKey: queryKeys.taxSummary(year),
    queryFn: () => fetchTaxSummary(year),
  })
}

/** Cash balance (RDN) and the return on the money put in. Refreshed with the portfolio. */
export function useCash() {
  return useQuery({ queryKey: queryKeys.cash, queryFn: fetchCash })
}

/** The user's holding notes, with flags (review due, target reached, stop hit). */
export function useNotes() {
  return useQuery({ queryKey: queryKeys.notes, queryFn: fetchNotes })
}
