# Forge admin web image — Vite/React build served by nginx. Multi-arch (amd64 + arm64).
# Build context = Project-source/forge-admin.
#   docker build -t forge-web:v1.0.0 .
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.30-alpine
# SPA + /admin-api reverse proxy; ${FORGE_API_UPSTREAM} substituted at start (NGINX_ENVSUBST_FILTER
# limits envsubst to FORGE_* so nginx's own $uri/$host are preserved).
ENV FORGE_API_UPSTREAM=forge-api:8080 \
    NGINX_ENVSUBST_FILTER=FORGE_
RUN rm -f /etc/nginx/conf.d/default.conf /usr/share/nginx/html/index.html
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 80
