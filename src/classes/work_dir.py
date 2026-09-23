"""The directory a run writes into: --workdir, else $HVLA_WORK_DIR, else the CWD.

resolve() chdir's into it, so the relative write sites (measurement_sets/, the
results folder, import.json, replay.py, the CASA log) land there and stay
relative -- an absolute path persisted into import.json or replay.py would not
replay on another machine.
"""
import os
import sys
from pathlib import Path

from classes.constants import MS_SUB_PATH

FLAG = '--workdir'
ENV_VAR = 'HVLA_WORK_DIR'

_work_dir = None


def resolve(argv=None):
  """Pick the work directory, create it, chdir into it, and return it.

  argv is scanned rather than parsed: this runs before argparse, which lives in
  a module that imports casatasks."""
  global _work_dir
  requested = _from_argv(sys.argv[1:] if argv is None else argv) or os.environ.get(ENV_VAR)
  target = Path(requested).expanduser() if requested else Path.cwd()
  try:
    target.mkdir(parents=True, exist_ok=True)
    target = target.resolve()  #absolute before the chdir, or a relative --workdir re-resolves
    os.chdir(target)
    (target / MS_SUB_PATH.strip('/')).mkdir(exist_ok=True)  #importvla won't create it
  except OSError as err:
    raise SystemExit(f"Cannot use work directory {target}: {err}")
  _work_dir = Path.cwd()
  return _work_dir


def current():
  """The work directory, or the CWD when resolve() has not run -- a module
  imported outside the entry point (any harnesses) still gets an answer."""
  return _work_dir or Path.cwd()


def path(*parts):
  """A path inside the work directory."""
  return current().joinpath(*parts)


def _from_argv(argv):
  """The --workdir value, or None. Accepts '=' and the abbreviated prefixes
  argparse accepts, so this scan and the real parse cannot disagree."""
  for index, arg in enumerate(argv):
    name, sep, value = arg.partition('=')
    if len(name) > 2 and FLAG.startswith(name):
      if sep:
        return value
      return argv[index + 1] if index + 1 < len(argv) else None
  return None
