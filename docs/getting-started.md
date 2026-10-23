# Getting started

## Run with Docker

```bash
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:5173 (nginx, serves the built SPA; this machine only) |
| Backend  | http://localhost:8000 (interactive API docs at `/docs`; this machine only) |

Both listen on this machine only. To use Bursa from your phone or another
computer, see [Access from other devices](#access-from-other-devices-tailscale).

The SQLite database lives at `./backend/data/bursa.db` and survives container restarts.
The first boot fetches ~1 year of daily candles, so initial charts fill in within a few seconds.
A few minutes later a background job extends every stock to 5 years of daily history
(`DAILY_HISTORY_YEARS`); it runs once per stock and takes a while on the first boot.

### First sign-in

Bursa is invite-only. On the first start the backend logs a one-time link that
creates the admin account:

```bash
docker compose logs backend | grep "Create the admin"
```

Open it and choose your name, email and password. Admin accounts need two-factor
authentication, so you're asked to set up an authenticator app (or email codes) and
to save your recovery codes before the app opens. Invite others from
**Settings → Users & invites** (account menu, top right). See
[Configuration → Accounts](configuration.md#accounts).

Optional extras (AI assistant, email, Telegram alerts) are enabled through
`backend/.env`: start from the template (`cp backend/.env.example backend/.env`);
see [Configuration](configuration.md).

## Access from other devices (Tailscale)

Bursa is meant to stay off the public internet. Reach it through
[Tailscale](https://tailscale.com) (free for personal use), which encrypts the
connection and only lets your own devices in:

1. Install Tailscale on the machine running Bursa and on your phone / laptop,
   signed in to the same account. In the Tailscale admin console, enable
   **MagicDNS** and **HTTPS certificates** (DNS page).
2. On the machine running Bursa, publish the app on your tailnet (it keeps
   running across restarts):

   ```bash
   tailscale serve --bg 5173
   ```

   It prints the address, e.g. `https://bursa-server.tail1234.ts.net`.
3. Tell Bursa that address, in `backend/.env`:

   ```env
   PUBLIC_URL=https://bursa-server.tail1234.ts.net
   ```

   and restart: `docker compose up -d`. Secure cookies switch on by themselves
   for an `https://` address; invite and reset links use it.

Open the address on any of your devices. To stop sharing:
`tailscale serve reset`.

Don't open port 5173 on your router or bind it to all interfaces instead: that
serves the sign-in page and your session over plain HTTP to whoever can reach
it. (`BURSA_BIND=0.0.0.0 docker compose up -d` does that, for a trusted home
network only.)

## Reset all data

Delete the database files and restart:

```bash
rm -f backend/data/bursa.db*
docker compose up --build
```

## Development (hot reload)

The Docker image is the optimized runtime. For live reload while coding, run the
dev servers directly (no separate compose file needed):

```bash
# Backend (auto-reload)
cd backend
pip install -r requirements.txt
python prepare.py                  # migrations + seed (again after pulling changes)
uvicorn main:app --reload --port 8000

# Worker (scheduler + syncs) — in another terminal; restart it after code changes
cd backend
python worker.py

# Frontend (Vite HMR) — in another terminal
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Vite serves on http://localhost:5173 and, with `VITE_API_URL` set, talks to the
backend on `:8000` (CORS is already allowed for `localhost:5173`). Without the worker
the app still works, but nothing syncs and Sync all waits for it.

Next: [Development commands](development.md).
