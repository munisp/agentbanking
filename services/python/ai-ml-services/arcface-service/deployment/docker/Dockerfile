# ArcFace Face Matching Service - Production Dockerfile
# Multi-stage build for optimized image size

# ============================================================================
# Stage 1: Base Image with CUDA Support
# ============================================================================
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 AS base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \
    libopencv-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user (non-root for security)
RUN useradd -m -u 1000 -s /bin/bash appuser

# ============================================================================
# Stage 2: Dependencies Installation
# ============================================================================
FROM base AS dependencies

# Set working directory
WORKDIR /tmp

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 3: Application Build
# ============================================================================
FROM base AS application

# Copy installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.10/dist-packages /usr/local/lib/python3.10/dist-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Set working directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/models \
             /app/logs \
             /app/cache \
             /var/log/arcface-service && \
    chown -R appuser:appuser /app /var/log/arcface-service

# Copy application code
COPY --chown=appuser:appuser . /app/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8004/api/v1/face-matching/health || exit 1

# Set entrypoint
ENTRYPOINT ["python3"]

# Default command (can be overridden)
CMD ["-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004", "--workers", "4"]

# ============================================================================
# Build Instructions:
# ============================================================================
# Build image:
#   docker build -t arcface-service:1.0.0 -f deployment/docker/Dockerfile .
#
# Run container (GPU):
#   docker run -d --name arcface-service --gpus all -p 8004:8004 \
#     -v $(pwd)/models:/app/models \
#     -e DEVICE=cuda \
#     arcface-service:1.0.0
#
# Run container (CPU):
#   docker run -d --name arcface-service -p 8004:8004 \
#     -v $(pwd)/models:/app/models \
#     -e DEVICE=cpu \
#     arcface-service:1.0.0
# ============================================================================

# Labels
LABEL maintainer="Platform Engineering Team" \
      version="1.0.0" \
      description="ArcFace Face Matching Service with 95%+ accuracy" \
      service="arcface-face-matching"
