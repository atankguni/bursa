# Running Bursa on the web

Bursa on a server with its own domain and HTTPS, reachable from any browser, and
running all the time: alerts, the daily email, the live track record and backups
only work while it runs.

```
browser ──https──▶ Caddy (80/443) ──▶ nginx (frontend) ──▶ backend API
                   certificates,        app files,            database,
                   HTTP → HTTPS          /api proxy,           worker jobs
                                         rate limits
```

Caddy is added by `docker-compose.web.yml`; it gets and renews a Let's Encrypt
certificate by itself. The frontend's port is no longer published, so HTTPS
through Caddy is the only way in; the backend only listens on the server's
loopback address.

Bursa stays invite-only, and Yahoo Finance's data is for personal, non-commercial
use: keep it to yourself and people you invite (see
[Third-party notices](third-party-notices.md)).

## What you need

- **A server** with Ubuntu 24.04, 2 GB of memory (the API idles at ~80 MB, the
  worker ~155 MB; building the images is the peak) and 20 GB of disk, in
  **Singapore or Jakarta** (close to IDX and to you).
- **A domain** (or a subdomain, e.g. `bursa.yourname.com`) whose DNS you control.
- **Email sending** (invites, password resets, 2FA codes by email, the daily
  summary): an SMTP mailbox or Resend, see [Configuration → Email](configuration.md).
- **Your backup key pair**: the age public key for `BACKUP_RECIPIENT`, with the
  private key in your password manager (never on the server).

## 1. Check Yahoo answers from the server

Do this first, on the new server (after step 3's Docker install and step 4's
clone): some datacenter addresses are throttled by Yahoo, and every price in
Bursa comes from it.

```bash
docker compose build backend
docker compose run --rm --no-deps backend python -m scripts.check_provider
```

All five checks should say `ok`. If they fail again an hour later, Yahoo is
blocking that address: try another region or provider before going further.

## 2. Point the domain at the server

At your DNS provider, add an **A** record (and **AAAA** for IPv6) for the name
you'll use, pointing at the server's address. Certificates can only be issued
once it resolves: `dig +short bursa.yourname.com` should print the address.

## 3. Prepare the server

As root, once:

```bash
# Your own user, with your SSH key (from your computer: ssh-copy-id bursa@<server>)
adduser bursa && usermod -aG sudo bursa

# Security updates install themselves
apt update && apt install -y unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades

# Firewall: SSH and web only
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443 && ufw enable

# Docker (official packages): https://docs.docker.com/engine/install/ubuntu/
usermod -aG docker bursa
```

After checking that `ssh bursa@<server>` works with your key, turn off
password and root logins:

```bash
printf 'PasswordAuthentication no\nPermitRootLogin no\n' > /etc/ssh/sshd_config.d/10-bursa.conf
systemctl reload ssh
```

Docker publishes ports past ufw's rules. Bursa only publishes 80 and 443 (Caddy)
and the backend on 127.0.0.1, so that's fine; keep it that way.

## 4. Get Bursa and configure it

As `bursa`:

```bash
git clone https://github.com/atankguni/bursa.git && cd bursa
```

`.env` next to `docker-compose.yml` (not committed):

```env
BURSA_DOMAIN=bursa.yourname.com
ACME_EMAIL=you@example.com
# Every `docker compose` command then includes the HTTPS layer.
COMPOSE_FILE=docker-compose.yml:docker-compose.web.yml
```

`backend/.env` (not committed), at least:

```env
PUBLIC_URL=https://bursa.yourname.com
BACKUP_RECIPIENT=age1...
GEMINI_API_KEY=...            # optional: the AI assistant
MAIL_PROVIDER=smtp            # and the other MAIL_ / SMTP_ settings
```

`PUBLIC_URL` with `https://` also makes the sign-in cookie HTTPS-only.

## 5. Bring your data (or start fresh)

To keep your accounts, portfolios and history, restore your latest encrypted
backup on the server ([Configuration → Backups](configuration.md#backups)):
copy `bursa-<time>.db.zst.age` and `bursa-<time>.secret.key.age` from your
current machine to `backend/data/backups/` on the server, put the private key
in a temporary file, run the restore steps, and delete the key file after.

Starting fresh instead: the first start logs a link to create the admin account
(`docker compose logs backend | grep "Create the admin"`).

## 6. Start

```bash
docker compose up -d --build
docker compose logs -f caddy     # "certificate obtained successfully", then Ctrl-C
```

Open `https://bursa.yourname.com`. With the restored database, sign in as before.

## 7. Copy backups off the server

Nightly backups are encrypted, so they can go to cloud storage. Install
[rclone](https://rclone.org/install/), set up a remote once (`rclone config`,
e.g. Google Drive as `gdrive`), then add to `crontab -e`:

```cron
15 4 * * * /home/bursa/bursa/deploy/offsite-backup.sh gdrive:bursa-backups
```

It copies only encrypted (`.age`) files. Check now and then that new ones arrive,
and restore one somewhere once to be sure.

## Updating

```bash
cd ~/bursa && git pull && docker compose up -d --build && docker image prune -f
```

Database migrations run by themselves when the backend starts.

## When something's wrong

| Symptom | Look at |
|---|---|
| No certificate / browser warning | `docker compose logs caddy`: DNS must point here and port 80 must be reachable from the internet |
| Page loads, data doesn't | `docker compose logs backend worker`; the Data health page (admins) |
| Prices stale | Rerun the Yahoo check above |
| Everyone shares one rate limit | IPv6 clients arriving through Docker's proxy: make sure `ip6tables` is on in Docker (default since Docker 27) |
