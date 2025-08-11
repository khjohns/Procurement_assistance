#!/bin/bash
# scripts/full_reset.sh

echo "🔄 Starting full cache reset..."

# 1. Stop all services
echo "⏹️ Stopping services..."
pkill -f "python.*gateway/main.py" 2>/dev/null
pkill -f "python.*src/" 2>/dev/null

# 2. Clear Python cache
echo "🗑️ Clearing Python cache..."
python scripts/clear_cache.py

# 3. Clear PostgreSQL cache
echo "💾 Clearing database cache..."
psql $DATABASE_URL -c "DISCARD ALL;" -c "DEALLOCATE ALL;"

# 4. Reset gateway
echo "🔧 Resetting gateway cache..."
python scripts/reset_gateway.py

# 5. Restart database with fresh setup
echo "🔨 Rebuilding database..."
python scripts/setup/run_db_setup.py setup

# 6. Wait for propagation
echo "⏳ Waiting for changes to propagate..."
sleep 3

# 7. Verify
echo "✅ Verifying setup..."
python scripts/setup/run_db_setup.py verify

echo "🎉 Cache reset complete!"