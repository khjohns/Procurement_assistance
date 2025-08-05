#!/bin/bash
# deploy_dynamic_system.sh

# Stopp scriptet hvis en kommando feiler
set -e

# Få rotmappen til prosjektet
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"
echo "Project root is: $PROJECT_ROOT"

# Aktiver virtual environment
echo "Activating virtual environment..."
source "$PROJECT_ROOT/venv/bin/activate"

# Gå til rotmappen for å sikre riktig kontekst
cd "$PROJECT_ROOT"

echo "Starting dynamic orchestration deployment..."

# 1. Start gateway
echo "Starting RPC Gateway..."
(cd src/gateway && python main.py &)
GATEWAY_PID=$!

# 2. Start spesialist-agenter som tjenester
echo "Starting specialist services..."
# Bruker -m for å kjøre moduler fra prosjektets rot
python -m src.specialists.agent_service --agent triage --port 8001 &
TRIAGE_PID=$!

python -m src.specialists.agent_service --agent protocol --port 8002 &
PROTOCOL_PID=$!

# 3. Vent på at tjenester er klare
echo "Waiting for services to start..."
sleep 5

# 4. Kjør database-migrering (KOMMENTERT UT)
# echo "Updating database schema..."
# psql $DATABASE_URL -f "$PROJECT_ROOT/sql/dynamic_orchestration_setup.sql"

# 5. Test at alt fungerer
echo "Running health checks..."
curl -f http://localhost:8000/health || { echo 'Gateway health check failed'; exit 1; }
curl -f http://localhost:8001/health || { echo 'Triage service health check failed'; exit 1; }
curl -f http://localhost:8002/health || { echo 'Protocol service health check failed'; exit 1; }

echo "Dynamic orchestration system deployed successfully!"
echo "Gateway PID: $GATEWAY_PID"
echo "Triage Service PID: $TRIAGE_PID"
echo "Protocol Service PID: $PROTOCOL_PID"

# Deaktiver venv til slutt
deactivate
