#!/bin/bash

# Browser Order Automation - Development Server
echo "Starting Browser Order Automation System"
echo "============================================="
echo ""

# Function to cleanup processes on exit
cleanup() {
    echo ""
    echo "Shutting down servers..."
    
    # Kill processes on specific ports
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    
    # Kill by process name
    pkill -f "uvicorn app:app" 2>/dev/null || true
    pkill -f "npm run dev" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    
    echo "✅ Cleanup completed"
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

# Check if Node.js is available
if ! command -v node >/dev/null 2>&1; then
    echo "❌ Node.js not found. Please install Node.js first."
    exit 1
fi

# Check if Python is available
if ! command -v python >/dev/null 2>&1; then
    echo "❌ Python not found. Please install Python first."
    exit 1
fi

# Clean up any existing processes on ports
echo "🧹 Cleaning up existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
sleep 2

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install frontend dependencies"
        exit 1
    fi
fi

# Check if package.json has dev script
if [ ! -f "frontend/package.json" ]; then
    echo "❌ frontend/package.json not found"
    exit 1
fi

# Install concurrently locally if not available
if [ ! -d "node_modules" ] || [ ! -d "node_modules/concurrently" ]; then
    echo "📦 Installing concurrently..."
    npm install concurrently
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install concurrently"
        exit 1
    fi
fi

# Create logs directory
mkdir -p logs

echo ""
echo "🌐 Server URLs:"
echo "   Backend API: http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo "   Settings: http://localhost:3000/settings"
echo ""
echo "📋 Log Files:"
echo "   Backend: logs/backend.log"
echo "   Frontend: logs/frontend.log"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Start both servers with improved logging and colored output
npx concurrently \
    --prefix "[{name}]" \
    --prefix-colors "cyan,magenta" \
    --names "Backend,Frontend" \
    --kill-others \
    --restart-tries 3 \
    --restart-after 3000 \
    --timestamp-format "HH:mm:ss" \
    --success first \
    "cd backend && PYTHONPATH=. python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload --reload-dir . --reload-include '*.py' --reload-exclude '*.pyc' --reload-exclude '__pycache__' --reload-exclude 'logs/*' --reload-exclude 'static/*' --log-level info --access-log --use-colors 2>&1 | tee ../logs/backend.log" \
    "cd frontend && BROWSER=none PORT=3000 npm run dev 2>&1 | tee ../logs/frontend.log"