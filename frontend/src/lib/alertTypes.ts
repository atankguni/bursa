import type { AlertType } from '../api'

/** The alert conditions, as offered on the Alerts page and in the stock pop-up. */
export const ALERT_TYPES: { value: AlertType; label: string }[] = [
  { value: 'price_above', label: 'Price above' },
  { value: 'price_below', label: 'Price below' },
  { value: 'pct_change', label: '% change ≥' },
  { value: 'rating_change', label: 'Signal change' },
  { value: 'dividend_soon', label: 'Dividend coming up' },
]

/** Conditions that need a number (a price, or a % move). */
export const THRESHOLD_TYPES: AlertType[] = ['price_above', 'price_below', 'pct_change']
