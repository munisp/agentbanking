FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY power_optimizer.py ./

RUN pip install --no-cache-dir flask flask-cors psutil

EXPOSE 8094

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8094/health || exit 1

CMD ["python", "power_optimizer.py"]
