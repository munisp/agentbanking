FROM python:3.12-slim-bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8032

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
CMD curl -f http://localhost:8032/health || exit 1

# Run the application
CMD ["python", "tigerbeetle_sync_manager.py"]
