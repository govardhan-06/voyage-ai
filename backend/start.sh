#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting Voyage AI Backend..."

# Activate virtual environment only if not already activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "Activating virtual environment..."
    source voyage/bin/activate
else
    echo "Virtual environment already activated: $VIRTUAL_ENV"
fi

# Start FastAPI app
uvicorn application:app --host 0.0.0.0 --port 8000 --reload