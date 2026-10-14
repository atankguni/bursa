// Centralised React Query keys (avoids stringly-typed drift across the app).
export const queryKeys = {
  indexes: ['indexes'] as const,
  stocks: (indexes: string[]) => ['stocks', indexes] as const,
  watchlist: ['watchlist'] as const,
  history: (ticker: string, range: string) => ['history', ticker, range] as const,
  fundamentals: (ticker: string) => ['fundamentals', ticker] as const,
}
