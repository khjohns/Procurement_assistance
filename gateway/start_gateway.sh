#!/bin/bash

# Check if port 8000 is in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "Port 8000 is already in use. Killing existing process..."
    lsof -ti:8000 | xargs kill -9
    sleep 2
fi

# Activate virtual environment (path adjusted for new location)
source ../venv/bin/activate

# Start gateway from within its directory
cd gateway

echo "Starting RPC Gateway on port 8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
