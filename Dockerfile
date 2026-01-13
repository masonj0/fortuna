# Use a Node.js base image to get Node and npm
FROM node:20-slim as frontend-builder

WORKDIR /app

# Copy frontend source and build it
COPY web_platform/frontend ./web_platform/frontend
RUN cd web_platform/frontend && npm ci && npm run build

# Use a Python base image for the final application
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY web_service/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY web_service/backend ./web_service/backend

# Copy the built frontend from the builder stage
COPY --from=frontend-builder /app/web_platform/frontend/out ./web_platform/frontend/out

# Create directories
RUN mkdir -p data json logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# Start monolith
CMD ["python", "web_service/backend/main.py"]
