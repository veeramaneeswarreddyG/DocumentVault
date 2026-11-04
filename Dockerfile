# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    UPLOAD_FOLDER=/app/uploads

# Install system dependencies (curl for container healthcheck, netcat/libpq dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create a dedicated non-root user and group
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/bash -m appuser

# Install Python dependencies first (leveraging Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY migrations/ ./migrations/
COPY wsgi.py .

# Create the uploads folder (Docker named volume target) and set permissions
RUN mkdir -p /app/uploads && \
    chmod +x scripts/entrypoint.sh && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose internal Flask/Gunicorn port
EXPOSE 5000

# Define container healthcheck
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Launch container via production entrypoint script
ENTRYPOINT ["scripts/entrypoint.sh"]
