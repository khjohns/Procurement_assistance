#!/bin/bash

# Sjekk om port 8000 er i bruk
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "Port 8000 is already in use. Killing existing process..."
    lsof -ti:8000 | xargs kill -9
    sleep 2
fi

# Aktiver virtual environment
source ../venv/bin/activate

# Start gateway
echo "Starting RPC Gateway on port 8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload