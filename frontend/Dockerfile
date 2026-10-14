# Bursa frontend — single multi-stage image: build the SPA, serve it with nginx.
#
#   Stage 1 (build): compiles the Vite/React app to static assets.
#   Stage 2 (serve): tiny nginx image serving `dist/`, gzipped, with /api
#                    reverse-proxied to the backend (same-origin -> no CORS).
#
# Local development does NOT use this image; run `npm run dev` (Vite HMR)
# instead. See README "Development".

# --- Stage 1: build -------------------------------------------------------
FROM node:26-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Empty base URL -> the client calls the API on its own origin (nginx proxied).
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --- Stage 2: serve -------------------------------------------------------
FROM nginx:alpine-slim
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
