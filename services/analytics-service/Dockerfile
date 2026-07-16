FROM python:3.12-slim-bookworm-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc postgresql-client && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY etl_pipeline_service.py .
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8087
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD python -c "import requests; requests.get('http://localhost:8087/health')"
CMD ["python", "etl_pipeline_service.py"]
