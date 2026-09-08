#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# CPU pinning (affinity). taskset CONFINES the run to these cores; on its own it
# does NOT parallelize anything. Leave empty (CPU_CORES="") to use all cores.
# ---------------------------------------------------------------------------
CPU_CORES="${HVLA_CPU_CORES-25,26,27,28}"   # e.g. "25,26,27,28" or "25-28"; empty disables pinning
                                           # set per install by tools/install_hvla_launcher.sh --cores

# ---------------------------------------------------------------------------
# MPI parallel launch (real CASA engine parallelism: tclean parallel=True, MMS).
# Auto-enabled only when BOTH an mpirun/mpiexec launcher AND a working mpi4py
# runtime are present; otherwise the run falls back to serial. Worker ranks are
# diverted into CASA's server loop the moment `casatasks` is imported (the entry
# point imports it first), so only rank 0 runs the pipeline + its prompts.
# This needs an MPI *runtime*, e.g.:  sudo apt install openmpi-bin libopenmpi-dev
# (the casampi/mpi4py pip packages are not enough on their own).
# ---------------------------------------------------------------------------
MPI_NPROC="${MPI_NPROC:-}"        # override rank count; default = #cores (1 client + rest workers)
MPI_BIND_ARGS="--bind-to none"    # OpenMPI: lets ranks honor the taskset affinity mask

PYTHON_CMD="python3.10"
VENV_NAME=".hvla_env"
DEPENDENCY_SCRIPT="src/Dependencies.py"
MAIN_SCRIPT="src/HVLA_image_machine.py"

# --- create the venv on first run ---
if [ ! -d "$VENV_NAME" ]; then
  if ! command -v "$PYTHON_CMD" >/dev/null 2>&1; then
    echo "Error: $PYTHON_CMD not found. Install Python 3.10 or change PYTHON_CMD." >&2
    exit 1
  fi
  echo "Creating virtual environment '$VENV_NAME' using $PYTHON_CMD..."
  "$PYTHON_CMD" -m venv "$VENV_NAME"
fi

# shellcheck disable=SC1091
source "$VENV_NAME/bin/activate"
PY="$VENV_NAME/bin/python"

echo "Running $DEPENDENCY_SCRIPT..."
"$PY" "$DEPENDENCY_SCRIPT"

# --- taskset prefix (CPU pinning), if requested and available ---
PIN=()
if [ -n "$CPU_CORES" ]; then
  if command -v taskset >/dev/null 2>&1; then
    PIN=(taskset --cpu-list "$CPU_CORES")
  else
    echo "Warning: taskset not found; running without CPU pinning." >&2
  fi
fi

# --- detect a usable MPI stack (a launcher AND an importable mpi4py runtime) ---
LAUNCHER=""
for c in mpirun mpiexec; do
  if command -v "$c" >/dev/null 2>&1; then LAUNCHER="$c"; break; fi
done
MPI_OK=0
if [ -n "$LAUNCHER" ] && "$PY" -c "import casampi; from mpi4py import MPI" >/dev/null 2>&1; then
  MPI_OK=1
fi

# --- derive rank count: #cores (1 client + the rest as CASA worker engines) ---
if [ -z "$MPI_NPROC" ]; then
  if [ -n "$CPU_CORES" ]; then
    # counts comma-listed cores, expanding "25-28" style ranges
    NCORES=$(tr ',' '\n' <<<"$CPU_CORES" | awk -F- 'NF==2{n+=$2-$1+1;next} NF==1&&$1!=""{n++} END{print n+0}')
  else
    NCORES=$(nproc 2>/dev/null || echo 4)
  fi
  MPI_NPROC=$((NCORES > 1 ? NCORES : 2))                 # need >=2 for a client + 1 worker
fi

echo "Running $MAIN_SCRIPT ..."
if [ "$MPI_OK" -eq 1 ]; then
  echo "Parallel mode: ${PIN[*]:-} $LAUNCHER $MPI_BIND_ARGS -n $MPI_NPROC | cores: ${CPU_CORES:-all}"
  # taskset wraps the launcher so every rank inherits the affinity mask; --bind-to none
  # stops OpenMPI from re-pinning ranks to cores outside that mask.
  exec ${PIN[@]+"${PIN[@]}"} "$LAUNCHER" $MPI_BIND_ARGS -n "$MPI_NPROC" "$PY" "$MAIN_SCRIPT" "$@"
else
 # echo "Serial mode: no usable MPI stack found."
  #echo "  Install an MPI runtime to enable parallel (e.g. 'sudo apt install openmpi-bin libopenmpi-dev'),"
 # echo "  then set parallel=True on the tclean call(s). Until then tclean runs serially."
  exec ${PIN[@]+"${PIN[@]}"} "$PY" "$MAIN_SCRIPT" "$@"
fi
