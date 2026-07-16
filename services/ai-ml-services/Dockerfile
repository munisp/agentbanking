FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

COPY requirements.txt* ./
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || \
    pip install --no-cache-dir fastapi uvicorn httpx redis aiohttp

COPY . .

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8150

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8150/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8150", "--workers", "2"]
