FROM python:3.12-slim-bookworm-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies
RUN pip install --no-cache-dir \
    httpx==0.25.2 \
    redis==5.0.1 \
    uvicorn[standard]==0.24.0

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["uvicorn", "analytics_service:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]

