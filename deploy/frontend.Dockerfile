# syntax=docker/dockerfile:1
#
# Build the Vue dashboard (apps/frontend_llmops) and serve the static bundle with
# nginx, which also reverse-proxies the API so the browser only talks to one
# origin (see deploy/nginx.conf).

# --- build stage ---
FROM node:22-alpine AS build
WORKDIR /app
COPY apps/frontend_llmops/package.json apps/frontend_llmops/package-lock.json ./
RUN npm ci
COPY apps/frontend_llmops/ ./
# Empty bases => the app calls same-origin /api (backend) and /v1 (router); nginx
# proxies them. So no host/port is baked in and the image is portable.
ENV VITE_API_BASE_URL="" \
    VITE_ROUTER_BASE_URL=""
RUN npm run build

# --- serve stage ---
FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
