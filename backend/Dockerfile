# Bursa backend — multi-stage so the runtime image carries only what runs.
#
#   build   : installs deps into /install, then strips what's never used at
#             runtime (bundled test suites, bytecode caches, debug symbols).
#   runtime : the production image (default target in docker-compose.yml).
#   test    : runtime + dev tools, for `docker build --target test` CI checks.

# --- build ------------------------------------------------------------------
FROM python:3.14-alpine AS build

# binutils -> `strip` for the compiled extensions.
RUN apk add --no-cache binutils

COPY requirements.txt .
# Optional async driver for a server database, e.g. --build-arg DB_DRIVER=asyncpg
# (PostgreSQL) or DB_DRIVER="aiomysql cryptography" (MySQL/MariaDB; MySQL 8
# logins need cryptography). SQLite needs none.
ARG DB_DRIVER=""
# --no-compile: no .pyc at install time (Python compiles on import anyway).
# All deps ship musllinux wheels, so no compiler/toolchain is required.
RUN pip install --no-cache-dir --no-compile --prefix=/install -r requirements.txt $DB_DRIVER \
 && find /install -depth -type d \( -name tests -o -name __pycache__ \) -exec rm -rf {} + \
 && find /install -type f \( -name '*.so' -o -name '*.so.*' \) -exec strip --strip-unneeded {} + \
 && find /install -type f \( -name '*.pyx' -o -name '*.pxd' -o -name '*.c' -o -name '*.h' \) -delete

# --- runtime ----------------------------------------------------------------
FROM python:3.14-alpine AS runtime

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
# so FastAPI logs stream straight to the terminal.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Jakarta

# tzdata   -> zoneinfo has no data in Alpine; APScheduler needs "Asia/Jakarta".
# libstdc++ -> runtime libs for numpy's musl wheel.
# pip is only needed to build, so it is removed from the runtime image.
RUN apk add --no-cache tzdata libstdc++ \
 && python -m pip uninstall -y pip \
 && rm -rf /root/.cache

COPY --from=build /install /usr/local

WORKDIR /app
COPY . .

# SQLite lives on a mounted volume.
RUN mkdir -p /app/data

EXPOSE 8000

# Production server (no --reload). For hot-reload during development, run
# uvicorn directly with the source mounted (see README "Development").
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

# --- test -------------------------------------------------------------------
# Same packages as production plus dev tools, and the PostgreSQL/MySQL drivers
# so the suite can also run against a server database (TEST_DATABASE_URL):
#   docker build --target test -t bursa-backend-test ./backend
#   docker run --rm bursa-backend-test
FROM runtime AS test
# nodejs: pyright's runtime (the pip package uses the system node when present).
# Dev tools come from requirements-dev.txt (its `-r requirements.txt` line is
# already satisfied by the runtime layer); the server DB drivers are extra.
COPY requirements.txt requirements-dev.txt /tmp/reqs/
RUN apk add --no-cache nodejs npm \
 && python -m ensurepip \
 && python -m pip install --no-cache-dir -r /tmp/reqs/requirements-dev.txt \
    asyncpg aiomysql cryptography
CMD ["sh", "-c", "ruff check . && pyright && python -m pytest -q"]
