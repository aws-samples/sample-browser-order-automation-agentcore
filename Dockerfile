# Multi-stage build for Python backend
FROM python:3.11-slim as backend-builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ ./py-backend/

# Frontend build stage
FROM node:18-alpine as frontend-builder

WORKDIR /app

# Copy frontend package files
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# Final runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies including Node.js for MCP server
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version \
    && mkdir -p /tmp/.npm /tmp/.cache \
    && chmod -R 777 /tmp/.npm /tmp/.cache

# Copy Python dependencies and backend
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin
COPY --from=backend-builder /app/py-backend ./py-backend

# Copy built frontend (not needed for backend-only container)
# COPY --from=frontend-builder /app/build ./frontend/build

# Set npm environment variables to use /tmp for cache
ENV NPM_CONFIG_CACHE=/tmp/.npm
ENV NPM_CONFIG_PREFIX=/tmp/.npm-global
ENV PATH=/tmp/.npm-global/bin:$PATH

# Create startup script
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'set -e' >> /app/start.sh && \
    echo 'export NPM_CONFIG_CACHE=/tmp/.npm' >> /app/start.sh && \
    echo 'export NPM_CONFIG_PREFIX=/tmp/.npm-global' >> /app/start.sh && \
    echo 'export PATH=/tmp/.npm-global/bin:$PATH' >> /app/start.sh && \
    echo 'echo "Starting Order Automation Backend..."' >> /app/start.sh && \
    echo 'echo "Node.js version: $(node --version)"' >> /app/start.sh && \
    echo 'echo "NPM version: $(npm --version)"' >> /app/start.sh && \
    echo 'cd /app/py-backend' >> /app/start.sh && \
    echo 'exec python -m uvicorn app:app --host 0.0.0.0 --port 8080' >> /app/start.sh && \
    chmod +x /app/start.sh

# Expose port
EXPOSE 8080

# Health check - try both endpoints
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || curl -f http://localhost:8080/api/health || exit 1

# Start the application
CMD ["/app/start.sh"]
