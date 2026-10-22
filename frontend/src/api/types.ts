// API types, generated from the backend's OpenAPI document (schema.gen.ts;
// regenerate with `make api-types`). These are friendlier names for the
// backend's Pydantic models: change a shape there, never here.

import type { components } from './schema.gen'

type Schemas = components['schemas']

// --- Stocks ----------------------------------------------------------------
export type Stock = Schemas['StockOut']
export type PricePoint = Schemas['PricePoint']
export type StockHistory = Schemas['StockHistory']
export type MarketIndex = Schemas['IndexOut']
export type IndexHistory = Schemas['IndexHistoryOut']
export type Fundamental = Schemas['FundamentalOut']
export type DerivedMetrics = Schemas['DerivedMetrics']
export type WatchlistItem = Schemas['WatchlistItemOut']
export type FundamentalsResponse = Schemas['FundamentalsResponse']
export type Valuation = Schemas['ValuationOut']
export type Dividend = Schemas['DividendOut']
export type DividendSummary = Schemas['DividendSummary']
export type Officer = Schemas['OfficerOut']
export type Company = Schemas['CompanyOut']

/** Chart span for daily bars; 5y/max load the stock's full history on first use. */
export type ChartSpan = '1m' | '3m' | '6m' | '1y' | '5y' | 'max'

// --- Recommendation --------------------------------------------------------
export type Category = Schemas['CategoryOut']
export type RecommendationSummary = Schemas['RecommendationSummary']
export type Recommendation = Schemas['RecommendationOut']
export type RatingRecord = Schemas['RatingRecordOut']
export type TrackRecord = Schemas['TrackRecordOut']
/** Long-term fundamentals vs short-term (swing, 1-4 weeks) price action. */
export type InvestingStyle = Schemas['PreferencesOut']['investing_style']

// --- AI assistant ------------------------------------------------------------
export type ChatTurn = Schemas['ChatTurn']
export type AssistantReply = Schemas['AssistantChatOut']
export type AssistantStatus = Schemas['AssistantStatusOut']
export type ChatSummary = Schemas['ChatSummaryOut']
export type SavedChatMessage = Schemas['ChatMessageOut']
export type ChatDetail = Schemas['ChatDetailOut']

// --- Preferences / status ------------------------------------------------------
/** The Settings-menu options saved per user (they follow you across devices). */
export type DisplaySettings = Schemas['DisplaySettings-Output']
export type Preferences = Schemas['PreferencesOut']
export type PreferencesInput = Schemas['PreferencesIn']
/** Broker costs in percent (defaults: typical Indonesian online broker). */
export type TradingCosts = Schemas['TradingCosts-Output']
export type MarketStatus = Schemas['MarketStatusOut']
export type Status = Schemas['StatusOut']

// --- Portfolio -------------------------------------------------------------
export type Transaction = Schemas['TransactionOut']
export type TransactionInput = Schemas['TransactionIn']
export type Holding = Schemas['HoldingOut']
export type PortfolioTotals = Schemas['PortfolioTotals']
export type Portfolio = Schemas['PortfolioOut']
/** A projected (not announced) dividend, from last year's ex-date. */
export type ExpectedDividend = Schemas['ExpectedDividendOut']
export type PortfolioRisk = Schemas['PortfolioRiskOut']
export type EquityPoint = Schemas['EquityPoint']

// --- Screener / search / market overview -----------------------------------
export type ScreenerRow = Schemas['ScreenerRow']
export type ScreenerPage = Schemas['ScreenerPage']
export type SyncStatus = Schemas['SyncStatusOut']
export type SyncStart = Schemas['SyncStartOut']
export type CatalogRow = Schemas['CatalogRow']
export type CatalogPage = Schemas['CatalogPage']
export type SearchResult = Schemas['SearchResultOut']
export type Mover = Schemas['MoverOut']
export type Sector = Schemas['SectorOut']
export type MarketOverview = Schemas['MarketOverviewOut']

// --- Alerts ----------------------------------------------------------------
export type AlertType = Schemas['AlertOut']['type']
export type Alert = Schemas['AlertOut']
export type AlertInput = Schemas['AlertIn']
export type AlertEvent = Schemas['AlertEventOut']
export type NotificationStatus = Schemas['NotificationStatusOut']

// --- Accounts ----------------------------------------------------------------
export type Me = Schemas['MeOut']
export type Role = Me['role']
export type TwoFactorChallenge = Schemas['TwoFactorChallengeOut']
export type TwoFactorMethod = TwoFactorChallenge['methods'][number]
export type LoginResult = Schemas['LoginOut']
export type TwoFactorStatus = Schemas['TwoFactorStatusOut']
export type TotpSetup = Schemas['TotpSetupOut']
export type AuthOptions = Schemas['AuthOptionsOut']
export type InviteInfo = Schemas['InviteInfoOut']
export type AdminUser = Schemas['UserOut']
export type PendingInvite = Schemas['PendingInviteOut']
/** A one-time link, shown once (the server keeps only its hash). */
export type OneTimeLink = Schemas['LinkOut']

// --- Data health -------------------------------------------------------------
export type DataHealth = Schemas['DataHealthOut']
export type JobHealth = Schemas['JobHealth']
export type HealthStatus = Schemas['JobsHealth']['status']
