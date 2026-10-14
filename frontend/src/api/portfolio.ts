import { api } from './client'
import type { EquityPoint, Portfolio, Transaction, TransactionInput } from './types'

export async function fetchPortfolio(): Promise<Portfolio> {
  const { data } = await api.get<Portfolio>('/api/portfolio')
  return data
}

export async function fetchTransactions(): Promise<Transaction[]> {
  const { data } = await api.get<Transaction[]>('/api/portfolio/transactions')
  return data
}

export async function addTransaction(input: TransactionInput): Promise<Transaction> {
  const { data } = await api.post<Transaction>('/api/portfolio/transactions', input)
  return data
}

export async function deleteTransaction(id: number): Promise<void> {
  await api.delete(`/api/portfolio/transactions/${id}`)
}

export async function fetchPortfolioHistory(): Promise<EquityPoint[]> {
  const { data } = await api.get<EquityPoint[]>('/api/portfolio/history')
  return data
}
