# Main Application Stage
FROM python:3.10.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY web_service/backend/requirements.txt /app/web_service/backend/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/web_service/backend/requirements.txt

# Copy backend code
COPY web_service/backend /app/web_service/backend
COPY web_service/__init__.py /app/web_service/

# Copy pre-built frontend assets
COPY web_service/frontend/public /app/web_service/frontend/public

# Create required directories
RUN mkdir -p /app/web_service/backend/data \
    && mkdir -p /app/web_service/backend/json \
    && mkdir -p /app/web_service/backend/logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Set entrypoint
WORKDIR /app
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["python", "-m", "web_service.backend.main"]
