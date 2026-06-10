FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8096
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8096/health')"
CMD ["uvicorn", "geofence_service:app", "--host", "0.0.0.0", "--port", "8096"]
