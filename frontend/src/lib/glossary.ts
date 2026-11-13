/**
 * Plain-language explanations of the numbers Bursa shows, for people who don't
 * read financial statements for fun. Shown by <Term> (a "?" next to a label) and
 * on the Glossary page. Keep each `short` to two or three sentences; `example`
 * uses round rupiah numbers.
 */

export interface GlossaryEntry {
  term: string
  short: string
  example?: string
  /** What a good value looks like, or how to read it. */
  read?: string
}

export const GLOSSARY = {
  pbv: {
    term: 'PBV (price to book value)',
    short:
      "The company's market value divided by its book value: what's left for shareholders if it sold everything it owns and paid all its debts.",
    example:
      'PBV 2 means you pay Rp 2 for every Rp 1 of the company’s net assets. PBV 0.8 means the market values it below its books.',
    read: 'Lower is cheaper, but a low PBV can mean the market doubts those assets or the profits. Compare it with the same company’s own history and with similar companies (banks with banks).',
  },
  per: {
    term: 'PER (price to earnings)',
    short: "The share price divided by a year's profit per share.",
    example:
      'PER 10 means that at today’s profit, the company earns back its price in 10 years.',
    read: 'Lower is cheaper. A very low PER can mean profits are expected to fall; a high one, that they are expected to grow.',
  },
  roe: {
    term: 'RoE (return on equity)',
    short: "A year's profit divided by the shareholders' money in the company (equity).",
    example: 'RoE 20% means every Rp 100 of shareholders’ money earned Rp 20 in a year.',
    read: 'Higher is better: above 15% is good for most IDX companies. Check that it holds up over several years and isn’t propped up by heavy debt (see Debt/Equity).',
  },
  net_margin: {
    term: 'Net margin',
    short:
      'Profit as a share of revenue: how much of each rupiah of sales the company keeps.',
    example: 'A 10% margin keeps Rp 10 of every Rp 100 sold.',
    read: 'Higher is better. Compare within an industry: supermarkets run on thin margins, software doesn’t.',
  },
  der: {
    term: 'Debt/Equity (DER)',
    short: 'How much the company owes compared with its shareholders’ money.',
    example: 'DER 0.5 means Rp 50 of debt for every Rp 100 of equity.',
    read: 'Lower is safer. Banks naturally have high ratios (deposits count as debt), so compare banks only with banks.',
  },
  equity_ratio: {
    term: 'Equity ratio',
    short:
      "The shareholders' share of everything the company owns; the rest is financed by debt.",
    read: 'Higher is safer: the company depends less on lenders.',
  },
  market_cap: {
    term: 'Market cap',
    short:
      'All the company’s shares × the share price: what the market says the whole company is worth.',
    read: 'Big companies tend to move more calmly and trade more easily; small ones can move a lot on little news.',
  },
  growth: {
    term: 'Revenue and earnings growth',
    short: 'How much sales and profit grew compared with the year before.',
    read: 'Steady growth over several years matters more than one jump.',
  },
  momentum: {
    term: 'Momentum',
    short:
      'How the price has been moving: the return over 3 months, the price against its 50-day average (SMA50), and where it sits between its 52-week low and high.',
    read: 'Stocks that have been rising tend to keep rising for a while, and falling ones to keep falling, but it reverses eventually.',
  },
  score: {
    term: 'Score (0–100)',
    short:
      'Where the stock ranks against the other rated IDX stocks on the categories below. 50 is the middle; 80 means it beats about 80% of them.',
    read: 'It is a comparison, not a prediction: in a falling market the best-ranked stock can still fall.',
  },
  rating: {
    term: 'Rating',
    short:
      'The score in words, from Very positive to Very negative. Long-term ratings use the company’s financials and price trend; short-term (trader) ratings only the last weeks’ price behaviour.',
    read: 'A starting point for your own research, not advice to buy or sell. The track record shows how past ratings did.',
  },
  conviction: {
    term: 'Conviction',
    short:
      'How clear-cut the rating is: high when the score is far from the middle, the categories agree with each other, and most of the data is there.',
    read: 'A "Positive" with weak conviction is a close call.',
  },
  coverage: {
    term: 'Data coverage',
    short: 'How many of the numbers behind the score were available for this stock.',
    read: 'Below about 70%, the score rests on less information: treat it with more care.',
  },
  percentile: {
    term: 'Percentile',
    short:
      'Where today’s value sits within its own past range: 0 is the lowest it has been, 100 the highest.',
    example: 'PBV at the 20th percentile means it was higher than today 80% of the time.',
  },
  quality: {
    term: 'Quality',
    short: 'How profitable the business is: RoE and net margin.',
  },
  valuation: {
    term: 'Valuation',
    short: 'How cheap the stock is for what you get: PBV and PER. Cheaper scores higher.',
  },
  health: {
    term: 'Health',
    short:
      'How much the company relies on debt: Debt/Equity and the equity ratio. Less debt scores higher.',
  },
  stability: {
    term: 'Stability',
    short:
      'How calmly the price has moved over the last 20 trading days. Calmer scores higher.',
  },
  setup: {
    term: 'Setup',
    short:
      'Where the price is within its last 20 days: near the high, rather than just bouncing off the low, scores higher.',
  },
  avg_cost: {
    term: 'Average cost',
    short:
      'What you paid per share on average, buy fees included. Each buy blends in; sales don’t change it.',
  },
  break_even: {
    term: 'Break-even price',
    short:
      'The lowest price at which selling all your shares gets your money back, after the sell fee and the 0.1% sales tax.',
  },
  settlement: {
    term: 'T+2 settlement',
    short:
      'On the IDX, money from a sale (and shares from a buy) arrives two trading days after the trade.',
  },
} satisfies Record<string, GlossaryEntry>

export type GlossaryId = keyof typeof GLOSSARY

/** The Glossary page's sections, in order; every entry is in one. */
export const GLOSSARY_GROUPS: { title: string; ids: GlossaryId[] }[] = [
  {
    title: 'Ratings',
    ids: ['score', 'rating', 'conviction', 'coverage', 'percentile'],
  },
  {
    title: 'Long-term categories',
    ids: ['quality', 'valuation', 'growth', 'momentum', 'health'],
  },
  { title: 'Short-term (trader) categories', ids: ['stability', 'setup'] },
  {
    title: 'Company numbers',
    ids: ['pbv', 'per', 'roe', 'net_margin', 'der', 'equity_ratio', 'market_cap'],
  },
  { title: 'Your portfolio', ids: ['avg_cost', 'break_even', 'settlement'] },
]

const isGlossaryId = (key: string): key is GlossaryId =>
  Object.prototype.hasOwnProperty.call(GLOSSARY, key)

/** A rating category name (from the API) → its entry, when there is one. */
export function categoryEntry(name: string): GlossaryId | null {
  const id = name.toLowerCase()
  return isGlossaryId(id) ? id : null
}
