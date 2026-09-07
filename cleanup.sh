#!/bin/bash
# Remove the scratch a run leaves behind. Results folders are archived output, so
# they are skipped unless --results is given.

set -u

REMOVE_RESULTS=0

usage() {
  cat <<'EOF'
Usage: ./cleanup.sh [--results]

  (no flags)  remove logs, listobs, MS directories and imaging products,
              leaving every *_results/ folder untouched
  --results   additionally delete the *_results/ folders themselves
  -h, --help  show this message
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --results) REMOVE_RESULTS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "cleanup.sh: unknown option '$1'" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

# -prune keeps the scrub out of the results folders: they hold copies with the same
# names (<name>.log, <name>.mask, <name>.pbcor.tt0, <name>-listobs.txt) and deleting
# those would gut the archived output. -exec rather than -delete, which implies -depth
# and cannot be combined with -prune.
scrub_files() { find . -name '*_results' -prune -o -type f -name "$1" -exec rm -f {} +; }
scrub_dirs()  { find . -name '*_results' -prune -o -type d -name "$1" -exec rm -rf {} +; }

# Remove .log and listobs files
scrub_files "*.log"
scrub_files "*-listobs.txt"

# Remove .ms directories
scrub_dirs "*.ms"
scrub_dirs "source.ms"
scrub_dirs "initial.ms"

# Remove .ms.flagversion directories
scrub_dirs "*.ms.flagversions"

# Remove .G0,B0 directories
scrub_dirs "*.G*"
scrub_dirs "*.B0"
scrub_dirs "*.fluxscale*"
scrub_dirs "*.selfcal*"
scrub_dirs "*.blcal_*"

#remove images
scrub_dirs "*.tt0"
scrub_dirs "*.mask"
scrub_dirs "TempLattice*"

#remove pb and pbcorimage
scrub_dirs "*.pb"
scrub_dirs "*.pbcorimage"

echo "Cleanup completed: removed .log, .ms, and .ms.flagversion files"

if [ "$REMOVE_RESULTS" -eq 1 ]; then
  shopt -s nullglob
  results=(*_results)
  if [ ${#results[@]} -eq 0 ]; then
    echo "No *_results folders to remove."
  else
    for folder in "${results[@]}"; do
      echo "Removing results folder: $folder"
      rm -rf "$folder"
    done
  fi
fi
