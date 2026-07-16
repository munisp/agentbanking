FROM python:3.12-slim-bookworm-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
CMD python -c "import requests; requests.get('http://localhost:5000/health')"

# Run the service
CMD ["python", "-m", "uvicorn", "src.gateway:app", "--host", "0.0.0.0", "--port", "5000"]

