FROM python:3.14-alpine

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
# so FastAPI logs stream straight to the terminal.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Jakarta

# tzdata   -> zoneinfo has no data in Alpine; APScheduler needs "Asia/Jakarta".
# libstdc++ -> runtime libs for numpy's musl wheel.
RUN apk add --no-cache tzdata libstdc++

WORKDIR /app

# Install Python deps first (better Docker layer caching). All deps ship
# musllinux wheels, so no compiler/toolchain is required.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application source.
COPY . .

# SQLite lives on a mounted volume.
RUN mkdir -p /app/data

EXPOSE 8000

# --reload enables hot-reloading when the source is bind-mounted in compose.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
