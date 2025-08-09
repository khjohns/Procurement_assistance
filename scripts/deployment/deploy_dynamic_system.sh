#!/bin/bash
# deploy_dynamic_system.sh

# Stop the script if a command fails
set -e

# Get the project root folder
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"
echo "Project root is: $PROJECT_ROOT"

# Activate virtual environment
echo "Activating virtual environment..."
source "$PROJECT_ROOT/venv/bin/activate"

# Go to the root folder to ensure correct context
cd "$PROJECT_ROOT"

echo "Starting dynamic orchestration deployment..."

# 1. Start gateway
echo "Starting RPC Gateway..."
(cd src/gateway && python main.py &)
GATEWAY_PID=$!

# 2. Start specialist agents as services
echo "Starting specialist services..."
# Use -m to run modules from the project root
python -m src.specialists.agent_service --agent triage --port 8001 &
TRIAGE_PID=$!

python -m src.specialists.agent_service --agent protocol --port 8002 &
PROTOCOL_PID=$!

# 3. Wait for services to be ready
echo "Waiting for services to start..."
sleep 5

# 4. Run database migration (COMMENTED OUT)
# echo "Updating database schema..."
# psql $DATABASE_URL -f "$PROJECT_ROOT/sql/dynamic_orchestration_setup.sql"

# 5. Test that everything works
echo "Running health checks..."
curl -f http://localhost:8000/health || { echo 'Gateway health check failed'; exit 1; }
curl -f http://localhost:8001/health || { echo 'Triage service health check failed'; exit 1; }
curl -f http://localhost:8002/health || { echo 'Protocol service health check failed'; exit 1; }

echo "Dynamic orchestration system deployed successfully!"
echo "Gateway PID: $GATEWAY_PID"
echo "Triage Service PID: $TRIAGE_PID"
echo "Protocol Service PID: $PROTOCOL_PID"

# Deactivate venv at the end
deactivate
