# API reference

The backend serves interactive OpenAPI docs at http://localhost:8000/docs.
`{ticker}` uses the Yahoo suffix, e.g. `BBCA.JK`.

Every endpoint needs a signed-in session (the `bursa_session` cookie from
`POST /api/auth/login`) except `/api/health` and the public `/api/auth` routes.
Without one the API answers `401`; **admin** endpoints answer `403` to other users.
An admin without two-factor authentication gets `403` with detail
`two_factor_setup_required` everywhere except `/api/auth/me` and `/api/auth/2fa`.
A browser locked after inactivity gets `423` with detail `session_locked` everywhere
except `/api/auth/me` (which answers with `locked: true`), `/unlock`, `/lock` and
`/logout`.
Watchlist, portfolio, alerts, preferences and the assistant act on the signed-in
user's own data. Writes from another site's page are refused (`403`).

## Auth

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/auth/options` | Public: whether reset-by-email is available, minimum password length |
| POST   | `/api/auth/login` | Sign in (`email`, `password`). Returns `{user}` and sets the session cookie, or `{two_factor}` (challenge `token`, `methods`) when a code is needed |
| POST   | `/api/auth/2fa/verify` | Public: finish signing in (`token`, `method`: totp/email/recovery, `code`, `remember_device`) |
| POST   | `/api/auth/2fa/resend` | Public: email a new sign-in code (once a minute) |
| GET    | `/api/auth/2fa` | Your 2FA status (methods, recovery codes left, remembered devices, required) |
| POST   | `/api/auth/2fa/totp` · `/totp/confirm` | Start authenticator setup (secret, `otpauth://` URI, QR SVG) / turn it on with a code |
| POST   | `/api/auth/2fa/email` · `/email/confirm` | Email a code / turn email codes on with it |
| POST   | `/api/auth/2fa/{totp,email}/disable` | Turn a method off (`password`) |
| POST   | `/api/auth/2fa/recovery-codes` | New recovery codes (`password`); shown once |
| DELETE | `/api/auth/2fa/trusted-devices` | Forget every remembered device |
| POST   | `/api/auth/logout` | Sign out this browser |
| GET    | `/api/auth/me` | The signed-in user (`locked`: the lock screen is due) |
| POST   | `/api/auth/active` | The page reports recent use (mouse, keyboard, touch); `423` once locked |
| POST   | `/api/auth/lock` | Lock this browser now |
| POST   | `/api/auth/unlock` | Unlock with `password` (no 2FA code); `LOCK_MAX_ATTEMPTS` wrong ones sign the browser out (`401`) |
| POST   | `/api/auth/password` | Change password (signs out other browsers) |
| GET    | `/api/auth/invites/{token}` | Public: check an invite link |
| POST   | `/api/auth/invites/{token}/accept` | Public: create the account (`name`, `password`; `email` for the setup link) and sign in |
| POST   | `/api/auth/password-reset` | Public: email a reset link (needs email set up) |
| GET/POST | `/api/auth/password-reset/{token}` | Public: check a reset link / set the new password |

## Admin

All admin only.

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/admin/users` | All accounts |
| PATCH  | `/api/admin/users/{id}` | Change `role` or `is_active` (not your own; one active admin always remains) |
| DELETE | `/api/admin/users/{id}` | Delete an account and its data |
| POST   | `/api/admin/users/{id}/reset-link` | One-time password reset link (also emailed if possible) |
| POST   | `/api/admin/users/{id}/reset-2fa` | Turn off a user's 2FA (lost phone and recovery codes) |
| GET/POST | `/api/admin/invites` | Pending invites / invite an email (`email`, `role`); returns the link |
| DELETE | `/api/admin/invites/{id}` | Revoke a pending invite |

## Meta

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/health` | Health check |
| GET    | `/api/status` | Global status (last sync, provider, session, counts) |
| GET    | `/api/market-status` | IDX trading status (open / break / closed) |
| GET    | `/api/providers` | Active data providers + registry |
| GET    | `/api/indexes` | Available index names |
| GET    | `/api/data-health` | Jobs, freshness, coverage, suspicious values (admin) |
| GET/PUT | `/api/preferences` | Your preferences: investing style, assistant access to your data, `assistant_save_chats` (`false` also deletes saved chats), `display` settings (camelCase, as the Settings menu), `alerts_seen_at` (only moves forward), `trading_costs` (buy/sell fee and dividend tax, %), `daily_digest` (summary email) |
| POST   | `/api/preferences/digest/preview` | Email today's summary to yourself now (409 without email or followed stocks) |

## Stocks

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/stocks?index=LQ45&index=IDX30` | Stocks (AND across indices) + latest price/change |
| POST   | `/api/stocks` | Track a new ticker |
| GET    | `/api/stocks/{ticker}` | Single tracked stock summary |
| GET    | `/api/stocks/{ticker}/history?interval=1d\|1m` | OHLCV bars for charts |
| GET    | `/api/stocks/{ticker}/fundamentals` | Yearly fundamentals + PBV/RoE |
| GET    | `/api/stocks/{ticker}/recommendation` | Buy-signal score + rating + conviction + factors |
| GET    | `/api/track-record` | How past ratings (your style) beat the median stock: backtest summary + live record |
| GET    | `/api/stocks/{ticker}/valuation` | PBV/RoE vs own history (percentile) |
| GET    | `/api/stocks/{ticker}/dividends` | Dividend history + trailing yield |
| GET    | `/api/stocks/{ticker}/company` | Company profile + board/management |
| POST/DELETE | `/api/stocks/{ticker}/track` | Add/remove a symbol from the intraday set |
| GET    | `/api/search?q=&all=` | Symbol search (IDX-only by default; `all=1` for every exchange) |
| GET    | `/api/catalog?q=&limit=&offset=` | Browse the full IDX catalog |

## Market and indices

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/market/overview` | Breadth, top movers, sector performance |
| GET    | `/api/indices` | Latest value + change of 33 IDX stock indices |
| GET    | `/api/indices/{code}/history?range=1y\|5y\|max` | Daily bars for one index |

## Screener

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/screener?min_score=&max_pbv=&min_roe=&rating=&sector=&buy_only=` | Rank/filter the universe |
| POST   | `/api/screener/sync` | Background sync of missing fundamentals (capped) |
| POST   | `/api/screener/sync?all=true` | Paced "sync all missing" |
| POST   | `/api/screener/sync/cancel` | Stop the running sync |
| GET    | `/api/screener/sync/status` | Progress of the sync job |

## Watchlist

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/watchlist` | Watchlist with price + fundamentals + ratios |
| POST   | `/api/watchlist/{ticker}` | Add a ticker (fetches fundamentals) |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |
| POST   | `/api/watchlist/refresh` | Re-sync all watchlist fundamentals |

## Portfolio

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/portfolio` | Holdings + totals (average-cost P/L) |
| GET/POST/DELETE | `/api/portfolio/transactions` | Manage transactions |
| GET    | `/api/portfolio/history` | Portfolio value over time |
| GET    | `/api/portfolio/risk` | Concentration, sectors, beta vs IHSG, stress test, drawdown |
| GET    | `/api/portfolio/dividend-calendar` | Expected (projected) dividends for holdings + watchlist |

## Alerts

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/alerts` | List / create alert rules (`dividend_soon`: threshold = days before the estimated cum date, default 3) |
| POST   | `/api/alerts/{id}/toggle` | Pause / resume an alert |
| DELETE | `/api/alerts/{id}` | Delete an alert |
| GET    | `/api/alerts/events` | Recent triggered alerts |
| GET    | `/api/alerts/notifications` | Telegram status |
| POST   | `/api/alerts/notifications/test` | Send a Telegram test message |

## Mail

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/mail/status` | Whether email is configured (provider, sender, recipient count, setup hint) (admin) |
| POST   | `/api/mail/test` | Send a test email to `MAIL_TO` (admin) |

## Assistant

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/assistant/status` | Whether the assistant is configured + usage |
| POST   | `/api/assistant/chat` | Ask a question (answers via read-only tools). Send `chat_id` to continue a saved chat; the answer returns the chat's id (`null` when saving is off) |
| GET    | `/api/assistant/chats` | Your saved chats, most recently used first |
| GET    | `/api/assistant/chats/{id}` | One chat with its messages (`404` once expired) |
| DELETE | `/api/assistant/chats/{id}` | Delete a chat |
| DELETE | `/api/assistant/chats` | Delete all your chats |
