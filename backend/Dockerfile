# Bursa backend — multi-stage so the runtime image carries only what runs.
#
#   build   : installs deps into /install, then strips what's never used at
#             runtime (bundled test suites, bytecode caches, debug symbols).
#   runtime : the production image (default target in docker-compose.yml).
#   test    : runtime + dev tools, for `docker build --target test` CI checks.

# --- build ------------------------------------------------------------------
# Python 3.14 on Alpine 3.24: patch releases come with each rebuild; moving to a
# new Python or Alpine release is a deliberate edit here.
FROM python:3.14-alpine3.24 AS build

# binutils -> `strip` for the compiled extensions.
RUN apk add --no-cache binutils

COPY requirements.txt .
# Optional async driver for PostgreSQL: --build-arg DB_DRIVER=asyncpg.
# SQLite needs none.
ARG DB_DRIVER=""
# --no-compile: no .pyc at install time (Python compiles on import anyway).
# All deps ship musllinux wheels, so no compiler/toolchain is required.
RUN pip install --no-cache-dir --no-compile --prefix=/install -r requirements.txt $DB_DRIVER \
 && find /install -depth -type d \( -name tests -o -name __pycache__ \) -exec rm -rf {} + \
 && find /install -type f \( -name '*.so' -o -name '*.so.*' \) -exec strip --strip-unneeded {} + \
 && find /install -type f \( -name '*.pyx' -o -name '*.pxd' -o -name '*.c' -o -name '*.h' \) -delete

# --- runtime ----------------------------------------------------------------
FROM python:3.14-alpine3.24 AS runtime

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
# so FastAPI logs stream straight to the terminal.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Jakarta

# tzdata -> zoneinfo has no data in Alpine; APScheduler needs "Asia/Jakarta".
# age    -> encrypts backups (BACKUP_RECIPIENT); age-keygen makes the key pair.
#           Its other two tools (inspect, passphrase plugin) are unused (-5 MB).
# (numpy's wheel bundles its own libstdc++, so the system one isn't needed.)
# Also removed, never used by a server: pip (build only), and the IDE, Tk,
# turtle demos and help() texts of the standard library (-5 MB).
RUN apk add --no-cache tzdata age \
 && rm /usr/bin/age-inspect /usr/bin/age-plugin-batchpass \
 && python -m pip uninstall -y pip \
 && cd /usr/local/lib/python3.14 \
 && rm -rf /root/.cache idlelib tkinter turtledemo pydoc_data lib-dynload/_tkinter*

COPY --from=build /install /usr/local

WORKDIR /app
COPY . .

# Runs as an unprivileged user (uid 1000). The mounted data directory must be
# writable by it: on Linux, `sudo chown -R 1000:1000 backend/data` once.
RUN addgroup -S -g 1000 bursa \
 && adduser -S -D -H -u 1000 -G bursa bursa \
 && mkdir -p /app/data \
 && chown bursa:bursa /app/data
USER bursa

EXPOSE 8000

# The API: prepare the database (migrations, seed) once, then serve with
# API_WORKERS processes (default 1). The worker process uses the same image
# with `python worker.py` (docker-compose.yml). For hot-reload during
# development, run uvicorn directly (see docs/getting-started.md).
CMD ["sh", "-c", "python prepare.py && exec uvicorn main:app --host 0.0.0.0 --port 8000 --no-access-log --workers ${API_WORKERS:-1}"]

# --- test -------------------------------------------------------------------
# Same packages as production plus dev tools, and the PostgreSQL driver so the
# suite can also run against PostgreSQL (TEST_DATABASE_URL):
#   docker build --target test -t bursa-backend-test ./backend
#   docker run --rm bursa-backend-test
FROM runtime AS test
# Dev tools need root to install; the suite runs against a bind-mounted
# checkout, so it stays root too (this image is never deployed).
USER root
# nodejs: pyright's runtime (the pip package uses the system node when present).
# Dev tools come from requirements-dev.txt (its `-r requirements.txt` line is
# already satisfied by the runtime layer); the PostgreSQL driver is extra.
COPY requirements.txt requirements-dev.txt /tmp/reqs/
RUN apk add --no-cache nodejs npm \
 && python -m ensurepip \
 && python -m pip install --no-cache-dir -r /tmp/reqs/requirements-dev.txt \
    asyncpg
CMD ["sh", "-c", "ruff check . && pyright && python -m pytest -q"]
