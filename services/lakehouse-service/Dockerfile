FROM python:3.12-slim-bookworm-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    libpq-dev \
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME for PySpark
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Copy requirements first for better caching
COPY requirements_complete.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies for production
RUN pip install --no-cache-dir \
    deltalake==0.14.0 \
    pyiceberg==0.5.1 \
    pyspark==3.5.0 \
    delta-spark==3.0.0 \
    kafka-python==2.0.2 \
    python-multipart==0.0.6 \
    uvicorn[standard]==0.24.0

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /data/lakehouse /data/checkpoints /spark-warehouse /iceberg-warehouse

# Expose port
EXPOSE 8070

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
CMD curl -f http://localhost:8070/health || exit 1

# Run the application
CMD ["uvicorn", "lakehouse_complete:app", "--host", "0.0.0.0", "--port", "8070", "--workers", "4"]

