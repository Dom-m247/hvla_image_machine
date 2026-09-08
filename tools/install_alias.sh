#!/usr/bin/env bash
# Add the hvla_image shell function to your shell rc. Run once, from inside your
# clone. The core list is required: run.sh pins with taskset, so two accounts left
# on the same cores would fight over them.
#
# Append-only: this never edits or deletes anything already in your rc. If the block
# is already there it says so and changes nothing.
#
#   bash tools/install_alias.sh --cores 25-28
#   bash tools/install_alias.sh --cores all --name hvla --rc ~/.zshrc
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME=hvla_image
RC="$HOME/.bashrc"
CORES=""
CORES_SET=0

usage() {
  cat <<'USAGE'
Usage: install_alias.sh --cores <list> [--name <fn>] [--rc <file>]

  --cores <list>  REQUIRED. CPU cores this account pins runs to. A comma list,
                  ranges, or a mix: 25,26,27,28 | 25-28 | 0-3,8. Use 'all' to
                  disable pinning and let runs use every core.
  --name <fn>     shell function name to define. Default: hvla_image
  --rc <file>     shell rc to append to. Default: ~/.bashrc (~/.zshrc for zsh)

To change your cores later, edit the HVLA_CPU_CORES line in the block this adds.
To undo it, delete the block -- it is fenced by two marked comment lines.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --cores) [ $# -ge 2 ] || { echo "install: --cores needs a value." >&2; exit 1; }
             CORES="$2"; CORES_SET=1; shift ;;
    --name)  [ $# -ge 2 ] || { echo "install: --name needs a value." >&2; exit 1; }
             NAME="$2"; shift ;;
    --rc)    [ $# -ge 2 ] || { echo "install: --rc needs a value." >&2; exit 1; }
             RC="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "install: unknown argument '$1'." >&2; usage >&2; exit 1 ;;
  esac
  shift
done

RC="${RC/#\~/$HOME}"   #--rc ~/.zshrc arrives literal when quoted
BEGIN="# >>> $NAME (HVLA Image Machine) >>>"
END="# <<< $NAME (HVLA Image Machine) <<<"

if [ "$CORES_SET" -eq 0 ]; then
  echo "install: --cores is required." >&2
  echo >&2
  usage >&2
  exit 1
fi

# 'all' is stored as empty, which is how run.sh spells "do not pin".
if [ "$CORES" = all ]; then
  CORES=""
elif ! [[ "$CORES" =~ ^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$ ]]; then
  echo "install: '$CORES' is not a core list. Expected 25,26,27,28 or 25-28 or 0-3,8 (or 'all')." >&2
  exit 1
fi

[ -f "$REPO/run.sh" ] || { echo "install: no run.sh at $REPO -- run this from inside the clone." >&2; exit 1; }

#already there: say so and stop rather than appending a second copy
if [ -f "$RC" ] && grep -Fqx "$BEGIN" "$RC"; then
  cat >&2 <<EOF
install: $NAME is already set up in $RC -- nothing changed.

To change your cores, edit the HVLA_CPU_CORES line in that block.
To reinstall, delete the block first (from the line
  $BEGIN
through its closing marker), then run this again.
EOF
  exit 0
fi

#the function cds in a subshell: run.sh resolves .hvla_env, src/ and data_archive/
#from the CWD, and the caller's shell must not be left in the repo afterwards
BLOCK="$BEGIN
# Runs the pipeline in $REPO from whatever directory you are in.
# HVLA_CPU_CORES: cores to pin to; empty means all cores. Edit and re-source to change.
$NAME() {
  ( cd \"$REPO\" && HVLA_CPU_CORES=\"$CORES\" bash run.sh \"\$@\" )
}
$END"

bash -n <<<"$BLOCK" || { echo "install: generated block is not valid shell; aborting." >&2; exit 1; }

touch "$RC"
#one blank line between the block and whatever precedes it
[ -s "$RC" ] && printf '\n' >> "$RC"
printf '%s\n' "$BLOCK" >> "$RC"

echo "added $NAME() to $RC"
echo "  repo:  $REPO"
echo "  cores: ${CORES:-all (pinning disabled)}"

case "${SHELL:-}" in
  *zsh) [ "$RC" = "$HOME/.bashrc" ] && echo "
NOTE: your login shell looks like zsh but this went into ~/.bashrc.
      Delete that block and re-run with --rc ~/.zshrc instead." ;;
esac

cat <<EOF

Activate it in this terminal:
  source $RC

Then, from anywhere:
  $NAME              # GUI, calibrate + image
  $NAME -rs          # search the archive, download, and run
  $NAME --noexport   # ...arguments pass straight through to run.sh
EOF
