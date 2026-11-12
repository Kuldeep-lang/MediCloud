# syntax=docker/dockerfile:1
# MediCloud web UI - multi-stage build.
#   build   : Node compiles the React app into static files
#   runtime : unprivileged nginx serves them and proxies /api to the backend

# ---------------------------------------------------------------- build
FROM node:24-alpine AS build
WORKDIR /app

# Dependencies first: cached until the lockfile changes.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# ---------------------------------------------------------------- runtime
FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime

ARG APP_VERSION=1.0.0
ARG GIT_COMMIT=unknown
LABEL org.opencontainers.image.title="medicloud-frontend" \
      org.opencontainers.image.description="MediCloud web UI (React, served by nginx)" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

# Patch OS packages (needs root briefly), then drop back to the nginx user.
USER root
RUN apk upgrade --no-cache
USER 101

# Rendered at start-up by the image's envsubst entrypoint (only the listed variables).
ENV BACKEND_UPSTREAM=http://backend:8000 \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1 \
    NGINX_ENVSUBST_FILTER="^(BACKEND_UPSTREAM|NGINX_LOCAL_RESOLVERS)$"

COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
