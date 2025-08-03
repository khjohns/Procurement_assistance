#!/bin/bash
# Activate MAIN PROJECT virtual environment and run MCP server
cd "$(dirname "$0")"

# Go up to main project directory
PROJECT_ROOT="$(dirname "$PWD")"

# Check if main venv exists
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "Error: Main project virtual environment not found at $PROJECT_ROOT/venv"
    exit 1
fi

# Activate main project venv
source "$PROJECT_ROOT/venv/bin/activate"

# Verify activation
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Failed to activate virtual environment"
    exit 1
fi

echo "Virtual environment activated: $VIRTUAL_ENV"
echo "Running MCP server..."

# Run the MCP server
python tools/mcp/claude_mcp_server.py "$@"