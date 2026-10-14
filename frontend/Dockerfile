# Development image for Vite + React.
# The source is bind-mounted by docker-compose so HMR works out of the box;
# node_modules is kept inside the container via an anonymous volume.
FROM node:20-alpine

WORKDIR /app

# Copy manifests first for better layer caching, then install deps.
COPY package.json ./
RUN npm install

# Copy the rest of the source (overridden by the compose bind mount in dev).
COPY . .

EXPOSE 5173

# --host makes the dev server reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
