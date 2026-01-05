#!/bin/bash

echo "🚀 Starting Project Setup..."

# 1. Python Environment Setup
echo "🐍 Setting up Python environment..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
if [ -f "server/requirements.txt" ]; then
    pip install -r server/requirements.txt
else
    echo "Warning: server/requirements.txt not found!"
fi

# 2. Server Environment Variables
if [ ! -f "server/.env" ] && [ -f "server/env.example" ]; then
    echo "Creating server/.env from example..."
    cp server/env.example server/.env
    echo "Created server/.env. Please update it with your API keys if necessary."
fi

# 3. Client Setup
echo "💻 Setting up Client (Node.js)..."
cd client
if [ -f "package.json" ]; then
    echo "Installing Node dependencies..."
    npm install
else
    echo "Warning: client/package.json not found!"
fi
cd ..

echo "✅ Setup complete!"
echo "To start the app, run: ./start.sh"
