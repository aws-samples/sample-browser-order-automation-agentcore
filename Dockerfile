# Multi-stage Dockerfile for Order Automation System
# Based on browser-control-with-nova-act best practices

# Stage 1: Python Backend Build
FROM python:3.11-slim as backend-builder

# Set working directory
WORKDIR /app

# Install system dependencies for Python
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    wget \
    gnupg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for Playwright and some Python packages)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Copy Python requirements
COPY py-backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps

# Stage 2: Node.js Frontend Build
FROM node:18-alpine as frontend-builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build the Next.js application
RUN npm run build

# Stage 3: Final Runtime Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for runtime
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin
COPY --from=backend-builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Copy built frontend from builder
COPY --from=frontend-builder /app/.next ./.next
COPY --from=frontend-builder /app/public ./public
COPY --from=frontend-builder /app/package*.json ./
COPY --from=frontend-builder /app/node_modules ./node_modules

# Copy backend application
COPY py-backend/ ./py-backend/

# Copy configuration files
COPY next.config.mjs ./
COPY tailwind.config.ts ./
COPY tsconfig.json ./
COPY components.json ./

# Create necessary directories
RUN mkdir -p /app/data/sessions \
    /app/logs \
    /app/assets/screenshots \
    ~/.nova_browser_profiles/base

# Set environment variables
ENV PYTHONPATH=/app/py-backend
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create startup script
RUN cat > /app/start.sh << 'EOF'
#!/bin/bash
set -e

echo "Starting Order Automation System..."

# Start Python backend
echo "📡 Starting Python backend on port 8000..."
cd /app/py-backend && python -m uvicorn app.app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Backend is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Backend failed to start within 30 seconds"
        exit 1
    fi
    sleep 1
done

# Start Next.js frontend
echo "🌐 Starting Next.js frontend on port 3000..."
cd /app && npm start &
FRONTEND_PID=$!

# Wait for frontend to be ready
echo "⏳ Waiting for frontend to be ready..."
for i in {1..30}; do
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        echo "✅ Frontend is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Frontend failed to start within 30 seconds"
        kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

echo "Order Automation System is running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   Health Check: http://localhost:8000/health"

# Function to handle shutdown
cleanup() {
    echo "🛑 Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    echo "✅ Shutdown complete"
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
EOF

RUN chmod +x /app/start.sh

# Expose ports
EXPOSE 3000 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health && curl -f http://localhost:3000 || exit 1

# Start the application
CMD ["/app/start.sh"]