#!/bin/bash
set -e

echo "Starting Order Automation System..."

# Check directories
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "Error: Backend or frontend directory not found!"
    exit 1
fi

# Setup Python environment
if [ ! -d "backend/venv" ]; then
    echo "Setting up Python virtual environment..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
else
    echo "Python environment found"
fi

# Setup Node.js dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing Node.js dependencies..."
    cd frontend
    npm install
    cd ..
else
    echo "Node.js dependencies found"
fi

# Create directories
mkdir -p logs

# Set environment
export PYTHONPATH="$(pwd)/backend"

# Start backend
echo "Starting Python backend on port 8000..."
cd backend
source venv/bin/activate
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Wait for backend
echo "Waiting for backend..."
for i in {1..30}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "Backend ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Backend failed to start"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# Start frontend
echo "Starting React frontend on port 3000..."
cd frontend
npm start &
FRONTEND_PID=$!
cd ..

# Wait for frontend
echo "Waiting for frontend..."
for i in {1..30}; do
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        echo "Frontend ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Frontend failed to start"
        kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
        exit 1
    fi
    sleep 2
done

echo ""
echo "Order Automation System is running!"
echo ""
echo "Frontend Dashboard: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo "Health Check: http://localhost:8000/health"
echo ""
echo "System Features:"
echo "  - Strands AI Agents for intelligent automation"
echo "  - Playwright MCP for structured browser control"
echo "  - Real-time WebSocket updates"
echo "  - Human-in-the-loop workflows"
echo "  - Multi-retailer support"
echo ""
echo "Press Ctrl+C to stop"

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    echo "Shutdown complete"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for processes
while true; do
    if ! kill -0 $BACKEND_PID 2>/dev/null || ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "Process died unexpectedly"
        cleanup
    fi
    sleep 5
done