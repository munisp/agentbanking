# ─────────────────────────────────────────────────────────────────────────────
# POS-54Link — application image
#
# The Node.js application lives in services/api-server-ts (it carries the only
# package.json + pnpm-lock.yaml in this repo after the 2026-06-29 monorepo
# restructure). The previous revision of this Dockerfile referenced a root
# package.json / pnpm-lock.yaml that no longer exist, breaking every build.
#
# Multi-stage: install → build → minimal runtime.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

# pnpm is provided by corepack; the exact version (10.4.1) is pinned by
# services/api-server-ts/package.json#packageManager.
RUN corepack enable

WORKDIR /app

# Copy manifests first for layer caching
COPY services/api-server-ts/package.json services/api-server-ts/pnpm-lock.yaml ./
# Lockfile restore pending (staged artifact for maintainers) — no-frozen for now
RUN pnpm install --no-frozen-lockfile

# Copy the application source (.dockerignore strips node_modules/dist/tests)
COPY services/api-server-ts/ ./

ENV NODE_ENV=production
# Full build = Vite client + esbuild server bundle. The client tree is not
# currently part of services/api-server-ts (vite.config.ts expects ./client),
# so fall back to the server-only bundle until the client is co-located.
RUN if [ -d client ]; then \
      pnpm build; \
    else \
      echo "client/ not present in services/api-server-ts — building server bundle only (pnpm build:server)"; \
      pnpm build:server; \
    fi

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS runtime

# Security: run as non-root
RUN addgroup -S posshell && adduser -S posshell -G posshell

WORKDIR /app

# Copy build output + migrations + manifests
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/drizzle ./drizzle
COPY --from=builder /app/package.json ./
COPY --from=builder /app/pnpm-lock.yaml ./

# NOTE: full install (not --prod). The esbuild bundle keeps runtime-external
# imports of dev-time packages (e.g. "vite" via server/_core/vite.ts), which
# must resolve when dist/index.js starts. Lockfile restore pending — no-frozen.
RUN corepack enable \
    && pnpm install --no-frozen-lockfile \
    && pnpm store prune

# Switch to non-root user
USER posshell

# Expose the server port (injected at runtime via PORT env var)
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -qO- http://localhost:${PORT:-3000}/api/health || exit 1

# Start the server bundle
CMD ["node", "dist/index.js"]
