# Bursa frontend — single multi-stage image: build the SPA, serve it with nginx.
#
#   Stage 1 (build): compiles the Vite/React app to static assets.
#   Stage 2 (serve): tiny unprivileged nginx serving `dist/`, gzipped, with /api
#                    reverse-proxied to the backend (same-origin -> no CORS).
#
# Local development does NOT use this image; run `npm run dev` (Vite HMR)
# instead. See README "Development".

# --- Stage 1: build -------------------------------------------------------
FROM node:26-alpine3.24 AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Empty base URL -> the client calls the API on its own origin (nginx proxied).
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --- Stage 2: serve -------------------------------------------------------
# The unprivileged nginx image: runs as uid 101, listens on 8080, keeps its pid
# and temp files in /tmp (so the container filesystem can be read-only).
FROM nginxinc/nginx-unprivileged:1.31-alpine3.24-slim
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
