#!/bin/bash
# Pj-OGUN launcher script
# Creates/activates a virtual environment and launches Streamlit

set -e

cd "$(dirname "$0")"

VENV_DIR=".venv"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install/update dependencies
echo "Installing dependencies..."
pip install -e . --quiet --upgrade

# Kill any existing Streamlit on port 8501
lsof -ti:8501 | xargs kill -9 2>/dev/null || true

echo "Starting Pj-OGUN at http://localhost:8501"
python -m streamlit run src/pj_ogun/ui/app.py "$@"
