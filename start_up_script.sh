#!/usr/bin/env bash
set -euo pipefail

PYTHON_CMD="python3.10"
VENV_NAME=".hvla_env"
SCRIPT="HVLA_image_machine.py"

# If venv exists, activate and run the HVLA script
if [ -d "$VENV_NAME" ]; then
  echo "Virtual environment '$VENV_NAME' already exists. Activating..."
  # shellcheck disable=SC1091
  source "$VENV_NAME/bin/activate"
  echo "Running $SCRIPT..."
  "$VENV_NAME/bin/python" "$SCRIPT"
  exit 0
fi

# Ensure the requested Python is available
if ! command -v "$PYTHON_CMD" >/dev/null 2>&1; then
  echo "Error: $PYTHON_CMD not found. Install Python 3.10 or change PYTHON_CMD."
  exit 1
fi

echo "Creating virtual environment '$VENV_NAME' using $PYTHON_CMD..."
"$PYTHON_CMD" -m venv "$VENV_NAME"

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source "$VENV_NAME/bin/activate"


echo "Virtual environment '$VENV_NAME' created and activated."
echo "Running $SCRIPT..."
"$VENV_NAME/bin/python" "$SCRIPT"
