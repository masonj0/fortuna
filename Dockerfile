FROM python:3.10-slim-bullseye

WORKDIR /app

# Install Node.js for frontend build
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy everything
COPY . .

# Build frontend
WORKDIR /app/web_platform/frontend
RUN npm ci && npm run build

# Copy frontend build to backend
WORKDIR /app
RUN mkdir -p web_service/backend/static && \
    cp -r web_platform/frontend/out/* web_service/backend/static/

# Install Python dependencies
WORKDIR /app
RUN pip install --no-cache-dir -r web_service/backend/requirements.txt

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/api/health', timeout=5)"

# Run backend
CMD ["python", "-m", "uvicorn", "web_service.backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
