# Configuration

Backend settings live in `backend/config.py` (Pydantic settings). Any of them can be
overridden with an environment variable or in `backend/.env`. That file is git-ignored
and Docker-ignored, and is passed to the container via `env_file`.
`backend/.env.example` is a commented template of the common settings: copy it to
`backend/.env` to start.

| What | Where |
|---|---|
| Ports, DB path, API URL | `docker-compose.yml` (`DATABASE_URL`, `VITE_API_URL`) |
| Tracked stocks & indices | `backend/market/tickers.py` |
| Retention days, staleness, CORS, time zone, **trading-session times** | `backend/config.py` |
| **Recommendation weights & rating thresholds** (investor and trader) | `backend/config.py` (`recommendation_*`) |
| IDX holidays | `backend/market/holidays.py` (update annually from the IDX calendar) |
| IDX lot size | `lot_size` (default 100) in `backend/config.py`; exposed via `/api/status` |
| Accounts: public URL, cookie, session and link lifetimes | `backend/config.py` (see [Accounts](#accounts)) |

## Processes

`docker compose up` starts the API (`backend`), the `worker` (scheduler and every
sync) and the frontend; see [Architecture → Processes](architecture.md#processes-api-and-worker).
The worker starts once the API is healthy (the API migrates the database first).

| Setting | Default | Meaning |
|---|---|---|
| `API_WORKERS` | `1` | API processes (uvicorn `--workers`). Raise it if pages get slow under many users; there is always exactly one worker. |

Worker logs: `docker compose logs -f worker`. If it isn't running, **Data health**
says so and nothing syncs until it is back (`docker compose up -d worker`).

## Database

SQLite is the default and needs no setup. PostgreSQL is the supported server
database (every check runs on both): set `DATABASE_URL` and build the backend with
its async driver:

| Database | `DATABASE_URL` | Build arg |
|---|---|---|
| SQLite (default) | `sqlite+aiosqlite:////app/data/bursa.db` | none |
| PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/bursa` | `DB_DRIVER=asyncpg` |

For example, in `docker-compose.yml`:

```yaml
  backend:
    build:
      context: ./backend
      args:
        DB_DRIVER: asyncpg
    environment:
      - DATABASE_URL=postgresql+asyncpg://bursa:secret@postgres:5432/bursa
```

The schema is created and upgraded automatically on startup (Alembic). Data is not
copied between databases: a new database starts empty and fills from the providers.
Your portfolio, watchlist and alerts would need to be moved separately.

### Backups

With SQLite, the backend backs up the database every night at 02:30 (Jakarta time):
a consistent copy taken while the app runs, checked with SQLite's integrity check
(a damaged copy is never kept), gzip-compressed, together with the 2FA server secret (`secret.key`; without it a restored
database can't read anyone's 2FA). The newest 7 are kept, readable by the owner only.

| Setting | Default | Meaning |
|---|---|---|
| `BACKUP_ENABLED` | `true` | Turn the nightly backup off |
| `BACKUP_DIR` | `./data/backups` | Where backups go (`backend/data/backups/` on the host, git-ignored) |
| `BACKUP_KEEP` | `7` | How many nightly backups to keep |

They sit on the same disk as the database, so they protect against mistakes and
corruption, not a lost disk: copy `backend/data/backups/` somewhere else now and then
(another drive or cloud storage). Back up now: `docker compose exec backend python -m services.backup`.

To restore one, stop the backend, unpack the backup into a new file (the restore
command checks it and never overwrites a file), then swap it in:

```bash
docker compose stop backend worker
docker compose run --rm --no-deps backend \
  python -m services.backup restore data/backups/bursa-2026-10-22_0230.db.gz data/bursa.restored.db
mv backend/data/bursa.db backend/data/bursa.before-restore.db   # keep until all is well
rm -f backend/data/bursa.db-wal backend/data/bursa.db-shm
mv backend/data/bursa.restored.db backend/data/bursa.db
cp backend/data/backups/bursa-2026-10-22_0230.secret.key backend/data/secret.key  # if present
docker compose start backend worker
```

A backup from before the 2026-10-23 schema change needs converting after the
restore (see [Development → Converting an old database](development.md#converting-an-old-database)).

PostgreSQL is not covered: use `pg_dump`.

## Accounts

Bursa is **invite-only** and every page needs a signed-in user. There is no sign-up:
an admin invites people from **Settings → Users & invites** (also in the account menu).

On a fresh install (no accounts yet) the backend logs a one-time link that creates the
first admin account:

```bash
docker compose logs backend | grep "Create the admin"
```

The link is regenerated on every start until it is used.

| Setting | Default | Meaning |
|---|---|---|
| `PUBLIC_URL` | `http://localhost:5173` | Where people open the app. Used in invite / reset links and trusted for writes (CSRF check) |
| `SESSION_COOKIE_SECURE` | `false` | Set `true` when the app is served over **HTTPS** (required for a public deployment) |
| `SESSION_DAYS` | `30` | A session expires after this many days without use |
| `INVITE_DAYS` | `7` | Invite links expire after this |
| `PASSWORD_RESET_HOURS` | `2` | Reset links expire after this |
| `PASSWORD_MIN_LENGTH` | `12` | Minimum password length |
| `PASSWORD_MIN_SCORE` | `3` | Strength a new password needs: [zxcvbn](https://github.com/dropbox/zxcvbn) score 0–4 (no "uppercase + digit + symbol" rules) |
| `PASSWORD_BREACH_CHECK` | `true` | Refuse passwords found in data breaches ([Have I Been Pwned](https://haveibeenpwned.com/Passwords)). Only the first 5 characters of the password's SHA-1 hash are sent; if the service can't be reached the check is skipped |
| `LOGIN_MAX_FAILURES` / `LOGIN_WINDOW_MINUTES` | `10` / `15` | Failed sign-ins allowed per email (3× per IP) before a pause |

**Forgot password** emails a reset link when [Email](#email-optional) is set up.
Without email, an admin creates a reset link for the user on the Users page and sends
it to them. Invite links work the same way: they are always shown to the admin, and
also emailed when email is set up.

Before exposing Bursa on the internet, put it behind HTTPS, set `PUBLIC_URL` to the
public address and `SESSION_COOKIE_SECURE=true`.

### Two-factor authentication

Required for admins (an admin without it only sees the setup screen), optional for
everyone else; set up from **Settings → Security** (also in the account menu).
Methods: an **authenticator app** (works without email), **email codes** (need
[Email](#email-optional)), and 10 single-use **recovery codes**. "Remember this device"
skips the code on that browser for a while. A password reset does not turn 2FA off;
an admin can reset a user's 2FA from the Users page.

| Setting | Default | Meaning |
|---|---|---|
| `SECRET_KEY` | *(generated)* | Server secret that encrypts authenticator secrets and keys the code hashes. Unset: created once in `SECRET_KEY_FILE` |
| `SECRET_KEY_FILE` | `./data/secret.key` | Where the generated secret lives (in the mounted `backend/data/`, git-ignored) |
| `MFA_ISSUER` | `Bursa` | Name shown in authenticator apps |
| `MFA_CODE_MINUTES` | `10` | A sign-in step / emailed code expires after this |
| `MFA_MAX_ATTEMPTS` | `5` | Wrong codes per sign-in attempt (they also count as failed sign-ins) |
| `TRUSTED_DEVICE_DAYS` | `30` | How long "Remember this device" lasts |

**Back up `backend/data/secret.key` together with the database.** Without it the
stored authenticator secrets and recovery codes can't be checked, and every user's
2FA has to be reset by an admin (or, for the last admin, by deleting the
`totp_secret` and `mfa_email` values in the `users` table).

## Data providers

`price_provider` / `fundamentals_provider` in `backend/config.py` select the source
(Yahoo today). Adapters live in `backend/market/providers/`. To switch sources, add
an adapter and register it in `market/providers/registry.py`.

## Rate-limiting

`provider_max_concurrency`, `provider_min_interval_ms`, `provider_chunk_size`,
`intraday_max_symbols` and `search_cache_seconds` in `backend/config.py`. See
[Architecture](architecture.md#architecture--rate-limiting) for how they interact.

## AI assistant (optional)

Put your key in `backend/.env`:

```env
GEMINI_API_KEY=...
```

A free key is available from Google AI Studio. Models, the daily question cap,
the tool-round cap and personal-data access are the `assistant_*` settings in
`backend/config.py`. Portfolio/watchlist access stays off unless you set
`assistant_personal_data=true`.

Chats are saved per user so they can be continued, and deleted a number of days
after their last message (an hourly job removes them):

```env
ASSISTANT_CHAT_DAYS=90
```

Each user can turn saving off in Settings → Investing, which also deletes their
saved chats.

Providers are abstracted in `backend/assistant/providers/`. Adding another LLM means
writing one adapter and registering it; the UI and API stay the same.

## Email (optional)

Email is disabled until a provider is configured in `backend/.env`. It is used for
invites, password resets and 2FA codes / security notices (all optional without it),
and is the delivery layer
future alerts, digests or reports will use.
Check the setup with `GET /api/mail/status`, and `POST /api/mail/test` sends a test
message to `MAIL_TO`.

**SMTP** works with any mailbox (Gmail / Google Workspace with an
[app password](https://myaccount.google.com/apppasswords), Outlook, Zoho) or a relay
such as Brevo or Mailgun:

```env
MAIL_PROVIDER=smtp
MAIL_FROM=Bursa <you@gmail.com>
MAIL_TO=you@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls   # or "ssl" on port 465, "none" for a local relay
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=your-app-password
```

**Resend** ([resend.com](https://resend.com), 3,000 free emails/month) needs a domain
verified in Resend for real delivery:

```env
MAIL_PROVIDER=resend
MAIL_FROM=Bursa <bursa@your-domain.com>
MAIL_TO=you@example.com
RESEND_API_KEY=re_...
```

**Console (development only)** prints every email (2FA codes, invites, reset links)
to the backend log instead of sending it, so these flows work without a mail account:

```env
MAIL_PROVIDER=console
```

```bash
docker compose logs -f backend | grep -A12 "DEV EMAIL"
```

Anyone who can read the logs can use those codes and links, so it only works while
`PUBLIC_URL` is localhost; on any other address it stays disabled. Remove it before
deploying.

`MAIL_TO` takes several comma-separated addresses. Providers live in `backend/mail/`;
adding one (Mailgun, SES, ...) means writing one adapter and registering it. See
[Architecture](architecture.md#email).

## Telegram alerts (optional)

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `backend/.env`. Step-by-step setup
is shown on the Alerts page (for admins), which can also send a test message. The chat
belongs to the server owner, so only **admins'** alerts are sent there; everyone's
alerts appear in the app.
