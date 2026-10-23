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
| `BURSA_BIND` | `127.0.0.1` | Address the frontend's port 5173 listens on (a shell / compose variable, not `backend/.env`). Keep the default and use Tailscale; `0.0.0.0` serves plain HTTP to your whole network |
| `API_WORKERS` | `1` | API processes (uvicorn `--workers`). Raise it if pages get slow under many users; there is always exactly one worker. |

The containers run without root (the backend as uid 1000, nginx as uid 101), with a
read-only filesystem and no Linux capabilities. The app writes only to
`backend/data/`, so on a **Linux** host that folder must belong to uid 1000 (once:
`sudo chown -R 1000:1000 backend/data`). Docker Desktop on macOS and Windows needs
nothing.

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
(a damaged copy is never kept), compressed with zstd (`.db.zst`, about a sixth of the
database's size; older `.db.gz` backups still restore), together with the 2FA server secret (`secret.key`; without it a restored
database can't read anyone's 2FA). The newest 7 are kept, readable by the owner only.

| Setting | Default | Meaning |
|---|---|---|
| `BACKUP_ENABLED` | `true` | Turn the nightly backup off |
| `BACKUP_DIR` | `./data/backups` | Where backups go (`backend/data/backups/` on the host, git-ignored) |
| `BACKUP_KEEP` | `7` | How many nightly backups to keep |
| `BACKUP_RECIPIENT` | *(unset)* | An [age](https://age-encryption.org) **public** key (`age1…`): backups are encrypted to it. Unset: plain backups (the log warns) |

They sit on the same disk as the database, so they protect against mistakes and
corruption, not a lost disk: copy `backend/data/backups/` somewhere else now and then
(another drive or cloud storage). Back up now: `docker compose exec backend python -m system.backup`.

#### Encrypting backups

A backup holds everything: accounts, portfolios and the 2FA server secret. Encrypt
them before they go to another drive or a cloud folder. Bursa uses
[age](https://age-encryption.org) with a key pair: the server only gets the
**public** key, so it can write backups but not read them, and a stolen backup (or
server) doesn't give them away.

1. Make a key pair (the image includes `age`):

   ```bash
   docker compose exec backend age-keygen
   ```

   It prints `# public key: age1…` and a line starting `AGE-SECRET-KEY-1…`.
   Save the **whole output** in your password manager, and don't leave it on
   the server. Lose it and the encrypted backups can't be opened.
2. Put the public key in `backend/.env`, then `docker compose up -d`:

   ```env
   BACKUP_RECIPIENT=age1...
   ```

New backups are `bursa-<time>.db.zst.age` and `bursa-<time>.secret.key.age`. Older
plain backups stay until they're pruned (delete them yourself to be rid of them
sooner). The restore below then needs the private key in a file for the moment, e.g.
`backend/data/restore-key.txt` (delete it afterwards), passed with
`--identity data/restore-key.txt`. Any other computer with `age` can open them too:
`age -d -i key.txt bursa-<time>.db.zst.age | zstd -d -o bursa.db` (macOS:
`brew install age zstd`).

To restore one, stop the backend, unpack the backup into a new file (the restore
command checks it and never overwrites a file), then swap it in:

```bash
docker compose stop backend worker
docker compose run --rm --no-deps backend \
  python -m system.backup restore data/backups/bursa-2026-10-22_0230.db.zst data/bursa.restored.db
mv backend/data/bursa.db backend/data/bursa.before-restore.db   # keep until all is well
rm -f backend/data/bursa.db-wal backend/data/bursa.db-shm
mv backend/data/bursa.restored.db backend/data/bursa.db
cp backend/data/backups/bursa-2026-10-22_0230.secret.key backend/data/secret.key  # if present
docker compose start backend worker
```

Encrypted (`.age`) backups: add `--identity data/restore-key.txt` to the restore
command, and decrypt the key file in place of the `cp`:

```bash
docker compose run --rm --no-deps backend age -d -i data/restore-key.txt \
  -o data/secret.key data/backups/bursa-2026-10-22_0230.secret.key.age
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
| `PUBLIC_URL` | `http://localhost:5173` | Where people open the app (with Tailscale: `https://<machine>.<tailnet>.ts.net`). Used in invite / reset links and trusted for writes (CSRF check) |
| `SESSION_COOKIE_SECURE` | `false` | Send the sign-in cookie over HTTPS only. Switched on automatically when `PUBLIC_URL` starts with `https://` |
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

Reach Bursa from other devices through Tailscale, not the open internet
([Getting started → Access from other devices](getting-started.md#access-from-other-devices-tailscale)).
If you ever do put it on the internet: HTTPS on a proxy in front of nginx, `PUBLIC_URL`
set to that address, and keep the port bound to `127.0.0.1` behind the proxy.

nginx also limits requests per address (`frontend/nginx.conf`): sign-in, codes,
reset emails and other changes under `/api/auth` to 10 a minute (a burst of 10),
and the whole API to 30 a second. Over the limit the app shows "Too many requests".
This sits in front of the app's own sign-in throttling (`LOGIN_MAX_FAILURES`).

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
| `SECURITY_LOG_DAYS` | `180` | How long the account activity log is kept |
| `LOCK_DEFAULT_MINUTES` | `15` | A browser locks after this many minutes without use, until the password is entered (no 2FA code). Each user can pick Off, 5, 15, 30 or 60 in Settings → Security |
| `LOCK_ADMIN_MAX_MINUTES` | `15` | Admin accounts can't turn the lock off or set a longer time |
| `LOCK_MAX_ATTEMPTS` | `5` | Wrong passwords on the lock screen before that browser is signed out |

### Screen lock

After `LOCK_DEFAULT_MINUTES` (or the user's own choice) without mouse, keyboard or
touch, the browser shows a lock screen and needs the password again; no 2FA code,
since that browser already passed it. Background price refreshes don't count as use.
The server enforces it too: the page reports use about once a minute, and an idle
session gets `423` on every request until it is unlocked, so removing the lock
screen in the browser's developer tools doesn't open anything. All tabs of a browser
lock and unlock together; other devices have their own timer. Locking clears the
data cached in the page. Unlocks and wrong passwords appear in the activity log, and
`LOCK_MAX_ATTEMPTS` wrong passwords sign that browser out.

### Devices and activity

**Settings → Security** lists the browsers signed in to your account (sign out one,
or all but the current one) and your recent activity: sign-ins, failed sign-ins,
password and 2FA changes, and what an admin changed on your account. Admins see
everyone's activity at the bottom of **Users & invites**.

A sign-in from a browser the account hasn't used before is marked **new device**,
and with [Email](#email-optional) set up the owner gets an email about it. Browsers
are told apart by a random cookie, not by address, so a phone moving between Wi-Fi
and mobile data isn't "new", while a new browser, a private window or cleared
cookies is.

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
