import type { Conviction, Rating } from '../api'

/**
 * What users see for a rating. The API keeps the internal codes (Strong Buy …
 * Avoid; alerts and filters use them); on screen they're described as a rank
 * against other stocks, not as buy/sell advice.
 */
export const RATING_LABEL: Record<Rating, string> = {
  'Strong Buy': 'Very positive',
  Buy: 'Positive',
  Hold: 'Neutral',
  Reduce: 'Negative',
  Avoid: 'Very negative',
}

/** Best first. */
export const RATING_ORDER: readonly Rating[] = [
  'Strong Buy',
  'Buy',
  'Hold',
  'Reduce',
  'Avoid',
]

export const ratingLabel = (rating: Rating) => RATING_LABEL[rating]

export const isPositive = (rating?: Rating | null) =>
  rating === 'Strong Buy' || rating === 'Buy'

/** Text colour for a rating (shared across Home / Watchlist / panels). */
export const ratingTone = (rating: Rating) =>
  isPositive(rating)
    ? 'text-bull'
    : rating === 'Reduce' || rating === 'Avoid'
      ? 'text-bear'
      : 'text-muted'

/** Conviction as 1-4 dots. */
export const CONVICTION_DOTS: Record<Conviction, number> = {
  Weak: 1,
  Moderate: 2,
  Strong: 3,
  'Very Strong': 4,
}
