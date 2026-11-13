import { api } from './client'
import type {
  EquityPoint,
  DividendIncome,
  ExpectedDividend,
  Portfolio,
  PortfolioRisk,
  TaxSummary,
  Cash,
  CashMovement,
  CashMovementInput,
  HoldingNote,
  HoldingNoteInput,
  Transaction,
  TransactionInput,
} from './types'

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

export async function fetchPortfolioRisk(): Promise<PortfolioRisk> {
  const { data } = await api.get<PortfolioRisk>('/api/portfolio/risk')
  return data
}

export async function fetchDividendIncome(): Promise<DividendIncome> {
  const { data } = await api.get<DividendIncome>('/api/portfolio/dividend-income', {
    timeout: 60_000, // may fetch dividend history for new tickers
  })
  return data
}

export async function fetchDividendCalendar(days = 180): Promise<ExpectedDividend[]> {
  const { data } = await api.get<ExpectedDividend[]>('/api/portfolio/dividend-calendar', {
    params: { days },
    timeout: 60_000, // first call may fetch dividend history for new tickers
  })
  return data
}

export async function fetchTaxSummary(year: number): Promise<TaxSummary> {
  const { data } = await api.get<TaxSummary>('/api/portfolio/tax-summary', {
    params: { year },
    timeout: 60_000, // may fetch dividend history for tickers without it
  })
  return data
}

export async function fetchCash(): Promise<Cash> {
  const { data } = await api.get<Cash>('/api/portfolio/cash')
  return data
}

export async function addCashMovement(input: CashMovementInput): Promise<CashMovement> {
  const { data } = await api.post<CashMovement>('/api/portfolio/cash', input)
  return data
}

export async function deleteCashMovement(id: number): Promise<void> {
  await api.delete(`/api/portfolio/cash/${id}`)
}

export async function fetchNotes(): Promise<HoldingNote[]> {
  const { data } = await api.get<HoldingNote[]>('/api/portfolio/notes')
  return data
}

export async function saveNote(
  ticker: string,
  input: HoldingNoteInput,
): Promise<HoldingNote> {
  const { data } = await api.put<HoldingNote>(
    `/api/portfolio/notes/${encodeURIComponent(ticker)}`,
    input,
  )
  return data
}

export async function deleteNote(ticker: string): Promise<void> {
  await api.delete(`/api/portfolio/notes/${encodeURIComponent(ticker)}`)
}
