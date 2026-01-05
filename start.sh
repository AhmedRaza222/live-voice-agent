#!/bin/bash

# Function to kill background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill $SERVER_PID 2>/dev/null
    exit
}

# Trap SIGINT (Ctrl+C)
trap cleanup SIGINT

echo "🚀 Starting Project..."

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Please run ./setup_mac.sh first."
    exit 1
fi

# Activate python env
source venv/bin/activate

# Start Python Server in background
echo "backend: Starting Python Server..."
python server/server.py &
SERVER_PID=$!

# Wait a moment for the server to potentially start
sleep 2

# Start Client
echo "frontend: Starting Client..."
cd client
npm run dev

# Wait for background process (in case npm run dev exits, though it usually doesn't)
wait $SERVER_PID
