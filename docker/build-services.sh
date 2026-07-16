#!/bin/bash
# Runs during docker build. Compiles Go/Rust services, installs Python/Node deps.
set -e

IFS=',' read -ra SVCLIST <<< "$SERVICES"

for svc in "${SVCLIST[@]}"; do
    svc=$(echo "$svc" | xargs)  # trim whitespace
    dir="/app/services/$svc"

    if [ ! -d "$dir" ]; then
        echo "[build] SKIP $svc — directory not found"
        continue
    fi

    echo "[build] Processing $svc..."

    if [ -f "$dir/go.mod" ]; then
        echo "[build] Go → $svc"
        cd "$dir"
        go mod download 2>/dev/null || true
        CGO_ENABLED=0 GOOS=linux go build -o /app/bin/$svc . 2>&1 || echo "[build] WARN: go build failed for $svc"
        if [ -f "/app/bin/$svc" ] && [ ! -x "/app/bin/$svc" ]; then
            echo "[build] WARN: $svc binary is not executable (library package?), removing"
            rm -f "/app/bin/$svc"
        fi

    elif [ -f "$dir/package.json" ]; then
        echo "[build] Node → $svc"
        cd "$dir"
        # Use pnpm for projects that declare it as packageManager
        if grep -q '"packageManager".*pnpm' "$dir/package.json" 2>/dev/null; then
            echo "[build] pnpm project detected for $svc"
            pnpm install --ignore-scripts 2>&1 || npm install 2>&1 || true
            # Prefer build:server (server-only, avoids frontend vite build failures)
            if node -e "const p=require('./package.json'); process.exit(p.scripts&&p.scripts['build:server']?0:1)" 2>/dev/null; then
                pnpm run build:server 2>&1 || true
            else
                pnpm run build 2>&1 || true
            fi
        else
            npm install 2>&1 || true
            if node -e "const p=require('./package.json'); process.exit(p.scripts&&p.scripts['build:server']?0:1)" 2>/dev/null; then
                npm run build:server 2>&1 || true
            else
                npm run build 2>&1 || true
            fi
            npm prune --production 2>&1 || true
        fi

    elif [ -f "$dir/requirements.txt" ]; then
        echo "[build] Python → $svc"
        pip install --no-cache-dir -r "$dir/requirements.txt" 2>&1 || echo "[build] WARN: pip install failed for $svc"
    fi
done

echo "[build] Cleaning build caches..."
go clean -modcache 2>/dev/null || true
pip cache purge 2>/dev/null || true
rm -rf /root/.cache /tmp/* 2>/dev/null || true

echo "[build] Done"
