"""What a failed run leaves behind.

Two things happen when a run fails: an event goes into the sweep's oversight
log, and everything diagnostic in the run directory is copied into
<sweep>/failed/<source>_<proj>_<seg>_<band>_failed/. The run directory itself is
moved, intact, into that folder as run/, so runs/ holds only runs that passed;
a resume moves it back and reuses it.
"""
import json
import re
import shutil
import traceback
from datetime import datetime
from pathlib import Path

from .runner import RUN_OUTPUT

#Files worth keeping from a failed run directory. Measurement sets, caltables and
#imaging products are deliberately absent: they are gigabytes each and they stay
#in the run directory anyway.
ARTIFACT_GLOBS = (RUN_OUTPUT, 'harness_seed.json', 'import.json',
                  'replay.py', 'casa-*.log', '*.log', '*-listobs.txt',
                  'measurement_sets/*-listobs.txt')
#...and from the results folder, which is copied whole minus its tarballs
SKIP_IN_RESULTS = ('.tar.gz', '.tar')
#a failed run's working directory, inside its failure folder
PARKED_RUN = 'run'


def failure_dir_name(selection):
  """<source>_<proj>_<seg>_<band>_failed.

  A source that never got as far as an observation has no project, and is
  named <source>_failed.
  """
  safe = re.sub(r'[^A-Za-z0-9.+-]+', '_', selection.name).strip('_') or 'source'
  if not selection.proj_code:
    return f"{safe}_failed"
  return (f"{safe}_{selection.proj_code}_{selection.segment or 'noseg'}_"
          f"{selection.band or 'noband'}_failed")


def record(result, failed_root, oversight, error=None, log=print):
  """Capture one failure: artifacts and the run directory to its own folder, an
  event to the oversight log. Points result.run_dir at where the run now is.

  `error` is an exception the harness itself raised (selection, download, seeding);
  a pipeline that ran and exited non-zero carries its reason on the result instead.
  """
  failed_root = Path(failed_root)
  target = failed_root / failure_dir_name(result.selection)
  target.mkdir(parents=True, exist_ok=True)

  copied = _copy_artifacts(result.run_dir, target)
  result.run_dir = _park(result.run_dir, target / PARKED_RUN, log)
  summary = _summary(result, error)
  (target / 'failure.json').write_text(json.dumps(summary, indent=2) + '\n')
  (target / 'failure.txt').write_text(_readable(summary))
  oversight.event('failure', status=result.status, source=summary['source'],
                  proj_code=summary['proj_code'], band=summary['band'],
                  detail=summary['detail'], artifacts=str(target))
  log(f"  captured {len(copied)} artifact(s) -> {target}")
  return target


def reclaim(selection, failed_root, run_dir, fresh=False):
  """Move a parked run directory back to `run_dir` before a retry, so the retry
  reuses its import. `fresh` discards it instead; the failure record stays."""
  parked = Path(failed_root) / failure_dir_name(selection) / PARKED_RUN
  if not parked.is_dir():
    return
  if fresh:
    shutil.rmtree(parked)
  elif not Path(run_dir).exists():
    Path(run_dir).parent.mkdir(parents=True, exist_ok=True)
    shutil.move(parked, run_dir)


def _park(run_dir, dest, log):
  """Move a failed run directory to `dest`; returns where it ends up."""
  run_dir = Path(run_dir)
  if not run_dir.is_dir():
    return run_dir
  try:
    if dest.exists():
      shutil.rmtree(dest)
    shutil.move(run_dir, dest)
  except Exception as exc:
    log(f"  run directory left in place: {run_dir} -> {dest}: {exc!r}")
    return run_dir
  return dest


def _summary(result, error):
  selection = result.selection
  summary = {
    'when': datetime.now().isoformat(timespec='seconds'),
    'source': selection.name,
    'alias': getattr(selection, 'alias', ''),
    'archive_name': getattr(selection, 'archive_name', ''),
    'proj_code': selection.proj_code,
    'segment': getattr(selection, 'segment', ''),
    'band': selection.band,
    'date': getattr(selection, 'date', ''),
    'config': getattr(selection, 'config', ''),
    'sensitivity': getattr(selection, 'sensitivity', ''),
    'archive_files': list(getattr(selection, 'archive_files', [])),
    'status': result.status,
    'returncode': result.returncode,
    'seconds': round(result.seconds, 1),
    'run_dir': str(result.run_dir),
    'detail': result.detail,
  }
  if error is not None:
    summary['exception'] = ''.join(
      traceback.format_exception(type(error), error, error.__traceback__)).strip()
  return summary


def _readable(summary):
  lines = [f"{summary['source']}  ({summary['proj_code']} seg "
           f"{summary['segment']}, band {summary['band']}, {summary['date']})",
           '=' * 72, '']
  for key in ('when', 'status', 'returncode', 'seconds', 'sensitivity',
              'archive_name', 'alias', 'run_dir'):
    lines.append(f"{key:<14}: {summary[key]}")
  lines += ['', 'archive files:']
  lines += [f"  {p}" for p in summary['archive_files']] or ['  (none)']
  lines += ['', 'reason:', f"  {summary['detail'] or '(none recorded)'}"]
  if 'exception' in summary:
    lines += ['', 'harness exception:', summary['exception']]
  return '\n'.join(lines) + '\n'


def _copy_artifacts(run_dir, target):
  run_dir = Path(run_dir)
  copied = []
  if not run_dir.is_dir():
    return copied
  #globs overlap (casa-*.log is also *.log), so collect first and copy each once
  wanted = {path for pattern in ARTIFACT_GLOBS
            for path in run_dir.glob(pattern) if path.is_file()}
  for path in sorted(wanted):
    dest = target / path.name
    shutil.copy2(path, dest)
    copied.append(dest)
  #the results folder, when the run got far enough to collect one
  for results in sorted(run_dir.glob('*_results')):
    dest = target / results.name
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(results, dest, ignore=_skip_tarballs, dirs_exist_ok=True)
    copied.append(dest)
  return copied


def _skip_tarballs(directory, names):
  return [n for n in names if n.endswith(SKIP_IN_RESULTS)]
