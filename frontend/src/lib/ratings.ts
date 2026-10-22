/**
 * What users see for a rating. The API keeps the internal codes (Strong Buy …
 * Avoid; alerts and filters use them); on screen they're described as a rank
 * against other stocks, not as buy/sell advice.
 */
export const RATING_LABEL: Record<string, string> = {
  'Strong Buy': 'Very positive',
  Buy: 'Positive',
  Hold: 'Neutral',
  Reduce: 'Negative',
  Avoid: 'Very negative',
}

export const RATING_ORDER = Object.keys(RATING_LABEL)

export const ratingLabel = (rating: string) => RATING_LABEL[rating] ?? rating

export const isPositive = (rating?: string | null) =>
  rating === 'Strong Buy' || rating === 'Buy'

/** Text colour for a rating (shared across Home / Watchlist / panels). */
export const ratingTone = (rating: string) =>
  isPositive(rating)
    ? 'text-bull'
    : rating === 'Reduce' || rating === 'Avoid'
      ? 'text-bear'
      : 'text-muted'
