# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web_service/frontend

# Copy package files
COPY web_service/frontend/package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Create next.config.js with static export
RUN cat > next.config.js << 'EOF'
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
}
module.exports = nextConfig
EOF

# Copy source
COPY web_service/frontend/src ./src
COPY web_service/frontend/public ./public

# Build
RUN npm run build

# Verify output
RUN if [ ! -f out/index.html ]; then echo "❌ Frontend build failed!"; exit 1; fi

# Stage 2: Build Backend
FROM python:3.10.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY web_service/backend/requirements.txt /app/web_service/backend/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/web_service/backend/requirements.txt

# Copy backend code
COPY web_service/backend /app/web_service/backend
COPY web_service/__init__.py /app/web_service/

# Copy frontend build from stage 1
COPY --from=frontend-builder /app/web_service/frontend/out /app/web_service/frontend/out

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
