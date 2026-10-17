# Getting started

## Run with Docker

```bash
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:5173 (nginx, serves the built SPA) |
| Backend  | http://localhost:8000 (interactive API docs at `/docs`) |

The SQLite database lives at `./backend/data/bursa.db` and survives container restarts.
The first boot fetches ~1 year of daily candles, so initial charts fill in within a few seconds.

### First sign-in

Bursa is invite-only. On the first start the backend logs a one-time link that
creates the admin account:

```bash
docker compose logs backend | grep "Create the admin"
```

Open it, choose your name, email and password, and you're in. Invite others from
**Users & invites** in the account menu (top right). See
[Configuration → Accounts](configuration.md#accounts).

Optional extras (AI assistant, email, Telegram alerts) are enabled through
`backend/.env`; see [Configuration](configuration.md).

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
uvicorn main:app --reload --port 8000

# Frontend (Vite HMR) — in another terminal
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Vite serves on http://localhost:5173 and, with `VITE_API_URL` set, talks to the
backend on `:8000` (CORS is already allowed for `localhost:5173`).

Next: [Development commands](development.md).
