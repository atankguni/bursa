# Development image for Vite + React (Node 26 = newest, LTS on 2026-10-28).
# The source is bind-mounted by docker-compose so HMR works out of the box;
# node_modules is kept inside the container via an anonymous volume.
FROM node:26-alpine

WORKDIR /app

# Copy manifests first for better layer caching, then install deps.
COPY package.json ./
RUN npm install

# Copy the rest of the source (overridden by the compose bind mount in dev).
COPY . .

EXPOSE 5173

# Re-sync deps on start (the node_modules volume can outlive package.json
# changes), then run the dev server reachable from outside the container.
CMD ["sh", "-c", "npm install --no-audit --no-fund && npm run dev -- --host 0.0.0.0 --port 5173"]
