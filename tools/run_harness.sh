#!/usr/bin/env bash
# Run a harness sweep with the pipeline's interpreter, from anywhere.
#
#   bash tools/run_harness.sh full-auto "3C 15" "3C 31, AL0405"
#   bash tools/run_harness.sh full-auto --targets-file names.txt --preset full_auto_selfcal
#   bash tools/run_harness.sh lightcurve "4C 35.03" --bands C
#   bash tools/run_harness.sh resume harnesses/sweeps/<sweep>
#   bash tools/run_harness.sh presets
#
# Arguments pass straight through to harnesses/run_harness.py (see harnesses/HARNESS.md).
# Sweeps go to harnesses/sweeps/ unless --sweeps-dir says otherwise; relative paths
# (--targets-file, a resume folder) resolve from your current directory.
#
# HVLA_CPU_CORES, when set, becomes --cores for a sweep that does not pass its own --
# the same variable run.sh pins to.
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
PY="$REPO/.hvla_env/bin/python"
HARNESS="$REPO/harnesses/run_harness.py"

[ -x "$PY" ] || { echo "run_harness: no pipeline interpreter at $PY -- run ./run.sh once to build it." >&2; exit 2; }
[ -f "$HARNESS" ] || { echo "run_harness: $HARNESS not found." >&2; exit 2; }

ARGS=("$@")
#--cores only exists on the sweep commands, not on 'presets'
case "${1:-}" in
  full-auto|lightcurve|resume)
    if [ -n "${HVLA_CPU_CORES:-}" ]; then
      given=0
      for arg in "$@"; do
        case "$arg" in --cores|--cores=*) given=1 ;; esac
      done
      [ "$given" -eq 1 ] || ARGS+=(--cores "$HVLA_CPU_CORES")
    fi
    ;;
esac

exec "$PY" "$HARNESS" ${ARGS[@]+"${ARGS[@]}"}
