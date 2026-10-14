import { api } from './client'
import type {
  CatalogRow,
  Company,
  DividendSummary,
  FundamentalsResponse,
  Recommendation,
  SearchResult,
  Stock,
  StockHistory,
  Valuation,
} from './types'

export async function fetchIndexes(): Promise<string[]> {
  const { data } = await api.get<string[]>('/api/indexes')
  return data
}

export async function fetchStocks(indexes?: string[]): Promise<Stock[]> {
  // Repeated `index` params (index=LQ45&index=IDX30); FastAPI reads them as a list.
  const params = new URLSearchParams()
  indexes?.forEach((i) => params.append('index', i))
  const { data } = await api.get<Stock[]>('/api/stocks', { params })
  return data
}

export async function fetchHistory(
  ticker: string,
  interval: '1d' | '1m' = '1d',
): Promise<StockHistory> {
  const { data } = await api.get<StockHistory>(`/api/stocks/${ticker}/history`, {
    params: { interval },
  })
  return data
}

export async function fetchFundamentals(
  ticker: string,
  refresh = false,
): Promise<FundamentalsResponse> {
  const { data } = await api.get<FundamentalsResponse>(
    `/api/stocks/${ticker}/fundamentals`,
    { params: refresh ? { refresh: true } : undefined },
  )
  return data
}

export async function fetchRecommendation(ticker: string): Promise<Recommendation> {
  const { data } = await api.get<Recommendation>(`/api/stocks/${ticker}/recommendation`)
  return data
}

export async function searchSymbols(q: string, all = false): Promise<SearchResult[]> {
  const { data } = await api.get<SearchResult[]>('/api/search', {
    params: { q, all },
  })
  return data
}

export async function fetchStock(ticker: string): Promise<Stock> {
  const { data } = await api.get<Stock>(`/api/stocks/${ticker}`)
  return data
}

export async function trackStock(ticker: string, name?: string): Promise<Stock> {
  const { data } = await api.post<Stock>('/api/stocks', { ticker, name })
  return data
}

export async function fetchValuation(ticker: string): Promise<Valuation> {
  const { data } = await api.get<Valuation>(`/api/stocks/${ticker}/valuation`)
  return data
}

export async function fetchDividends(ticker: string): Promise<DividendSummary> {
  const { data } = await api.get<DividendSummary>(`/api/stocks/${ticker}/dividends`)
  return data
}

export async function fetchCompany(ticker: string): Promise<Company> {
  const { data } = await api.get<Company>(`/api/stocks/${ticker}/company`)
  return data
}

export async function fetchCatalog(
  q?: string,
  limit = 100,
  offset = 0,
): Promise<CatalogRow[]> {
  const { data } = await api.get<CatalogRow[]>('/api/catalog', {
    params: { q: q || undefined, limit, offset },
  })
  return data
}

export async function setTracked(ticker: string, tracked: boolean): Promise<CatalogRow> {
  const { data } = tracked
    ? await api.post<CatalogRow>(`/api/stocks/${ticker}/track`)
    : await api.delete<CatalogRow>(`/api/stocks/${ticker}/track`)
  return data
}
