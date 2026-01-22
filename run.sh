#!/usr/bin/env bash
set -euo pipefail

CPU_CORES="25,26,27,28" #Delete,comment me out or change to dedsignated cores!


PYTHON_CMD="python3.10"
VENV_NAME=".hvla_env"
DEPENDENCY_SCRIPT="src/Dependencies.py"
MAIN_SCRIPT="src/HVLA_image_machine.py"
SYS_ARG=""


#check if args exist

if [ "$#" -ge 1 ]; then
  SYS_ARG="$1"
fi

# If venv exists, activate and run the HVLA script
if [ -d "$VENV_NAME" ]; then
  #echo "Virtual environment '$VENV_NAME' already exists. Activating..."
  # shellcheck disable=SC1091
  source "$VENV_NAME/bin/activate"
  echo "Running $DEPENDENCY_SCRIPT..."
  "$VENV_NAME/bin/python" "$DEPENDENCY_SCRIPT"
  echo "Running $MAIN_SCRIPT..."
  "taskset" "--cpu-list" "$CPU_CORES" "$VENV_NAME/bin/python" "$MAIN_SCRIPT" "$SYS_ARG"
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
echo "Running $DEPENDENCY_SCRIPT..."
"$VENV_NAME/bin/python" "$DEPENDENCY_SCRIPT"
echo "Running $MAIN_SCRIPT..."
  "taskset" "--cpu-list" "$CPU_CORES" "$VENV_NAME/bin/python" "$MAIN_SCRIPT" "$SYS_ARG"

