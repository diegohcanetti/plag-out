#!/bin/bash
# run_daily.sh
# Local entrypoint to trigger the full Plag-out ETL and ML pipeline manually.

set -e

echo "========================================="
echo "Starting Plag-out Daily Pipeline Execution"
echo "========================================="

# 1. Load local environment variables if .env exists
if [ -f .env ]; then
    echo "Loading environment variables from .env..."
    # Export variables from .env, ignoring commented lines
    export $(grep -v '^#' .env | xargs)
else
    echo "⚠️ Warning: .env file not found. Using default environment variables."
fi

# 2. Activate Python Virtual Environment
if [ -d venv ]; then
    echo "Activating virtual environment (venv)..."
    source venv/bin/activate
elif [ -d .venv ]; then
    echo "Activating virtual environment (.venv)..."
    source .venv/bin/activate
else
    echo "⚠️ Warning: Virtual environment not found. Running in global context."
fi

# 3. Verify Python dependencies
echo "Verifying python-dotenv..."
python -c "import dotenv" || pip install python-dotenv

# 4. Execute ETL pipeline
echo "Executing ETL Pipeline..."
PYTHONPATH=. python orchestrator.py

# 5. Execute ML prediction pipeline
echo "Executing ML Prediction Pipeline..."
PYTHONPATH=. python ml/run_ml_pipeline.py

echo "========================================="
echo "Pipeline execution finished successfully!"
echo "========================================="
