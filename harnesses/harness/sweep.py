"""One sweep: a harness kind, a preset and a list of targets, in a folder of its own.

    sweeps/<kind>_<preset>_<YYYYmmdd-HHMMSS>/
      sweep.json        the resolved preset, options and targets -- what resume rebuilds from
      manifest.json     the selections, so the pipeline phase can be resumed without searching
      oversight.log     every event of the sweep, one line each, written as it happens
      oversight.jsonl   the same events, machine-readable
      report.json       the summary, rewritten at the end of every pass
      runs/<slug>/      each run's working directory, ending in its own *_results/
      failed/<slug>_failed/  what a failed run left behind

Selection is serial (one radio_search2 session); runs go out in parallel batches.
A failure anywhere is an event and a result, never an exception that ends the
sweep: the runs beside it carry on.
"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import failures, runner, seed
from .kinds import KINDS
from .presets import Preset
from .selection import Selection, SelectionError, Selector, Target, download, read_manifest, write_manifest

SWEEPS_DIR = Path(__file__).resolve().parent.parent / 'sweeps'
SWEEP_FILE = 'sweep.json'


# ------------------------------------------------------------------ oversight
class Oversight:
  """The sweep's running log. Appended from every worker, flushed per event, so a
  sweep that dies still leaves a readable account of how far it got."""

  def __init__(self, root):
    self.log_path = Path(root) / 'oversight.log'
    self.jsonl_path = Path(root) / 'oversight.jsonl'
    self._lock = threading.Lock()

  def event(self, kind, **fields):
    record = {'when': datetime.now().isoformat(timespec='seconds'), 'event': kind, **fields}
    text = '  '.join(f"{k}={v}" for k, v in fields.items() if v not in ('', None, []))
    with self._lock:
      with open(self.log_path, 'a') as handle:
        handle.write(f"{record['when']}  {kind:<14} {text}\n")
      with open(self.jsonl_path, 'a') as handle:
        handle.write(json.dumps(record) + '\n')

  def last_status(self):
    """{run slug: the status its most recent run-end recorded}."""
    status = {}
    try:
      lines = self.jsonl_path.read_text().splitlines()
    except OSError:
      return status
    for line in lines:
      try:
        record = json.loads(line)
      except json.JSONDecodeError:
        continue   #a line cut short by a killed sweep
      if record.get('event') == 'run-end':
        status[record.get('slug')] = record.get('status')
    return status


# ---------------------------------------------------------------------- sweep
@dataclass
class Sweep:
  root: Path
  kind: str
  preset: Preset
  options: dict
  targets: list

  @property
  def runs_dir(self):
    return self.root / 'runs'

  @property
  def failed_dir(self):
    return self.root / 'failed'

  @property
  def manifest(self):
    return self.root / 'manifest.json'

  @property
  def report_path(self):
    return self.root / 'report.json'

  @classmethod
  def create(cls, sweeps_dir, kind, preset, options, targets):
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    root = Path(sweeps_dir) / f"{kind}_{preset.name}_{stamp}"
    root.mkdir(parents=True, exist_ok=False)
    sweep = cls(root, kind, preset, options, targets)
    (root / SWEEP_FILE).write_text(json.dumps({
      'created': datetime.now().isoformat(timespec='seconds'),
      'harness': kind,
      #the preset as it was, not a pointer to it: editing the file later must not
      #change what a resume of this sweep runs
      'preset': preset.to_dict(),
      'options': options,
      'targets': [t.to_dict() for t in targets],
    }, indent=2) + '\n')
    return sweep

  @classmethod
  def open(cls, root, overrides=None):
    root = Path(root)
    data = json.loads((root / SWEEP_FILE).read_text())
    stored = data['preset']
    preset = Preset(name=stored['name'], path=Path(stored['path']),
                    harness=stored['harness'], label=stored.get('label', ''),
                    options=stored.get('options', {}), seed=stored.get('seed', {}))
    options = {**data['options'],
               **{k: v for k, v in (overrides or {}).items() if v is not None}}
    return cls(root, data['harness'], preset, options,
               [Target(**t) for t in data['targets']])


# -------------------------------------------------------------- selection phase
def select(sweep, kind, oversight):
  """Choose and download every run of every target.

  Returns (selections, skipped). skipped are labels that could not be made
  runnable -- an unresolvable name, an empty segment, a failed download -- each
  recorded as it happens while the rest carry on.
  """
  options = sweep.options
  selections, skipped, seen = [], [], set()
  try:
    selector = Selector(before_year=options['before_year'])
    selector.__enter__()
  except Exception as exc:
    print(f"!! could not open a radio_search session: {exc!r}")
    for target in sweep.targets:
      _selection_failed(sweep, oversight, Selection(name=target.name), exc)
      skipped.append(target.label)
    return [], skipped

  try:
    for number, target in enumerate(sweep.targets, 1):
      print(f"\n=== Selection {number}/{len(sweep.targets)}: {target.label} ===")
      try:
        chosen, rejected = kind.choose(selector, target, options)
      except Exception as exc:
        reason = 'no usable observation' if isinstance(exc, SelectionError) else 'selection failed'
        print(f"  !! {reason}: {exc}")
        _selection_failed(sweep, oversight, Selection(name=target.name), exc)
        skipped.append(target.label)
        continue
      for label, why in rejected:
        print(f"  -- {label}: {why}")
        oversight.event('skipped', target=target.name, run=label, reason=why)
        skipped.append(f"{target.name}: {label}")
      if options['limit']:
        chosen = chosen[:options['limit']]
      #the same run reached twice (a source listed twice, or once per project) runs once
      chosen = [s for s in chosen if s.slug not in seen]
      seen.update(s.slug for s in chosen)
      _print_table(chosen)
      for selection in chosen:
        oversight.event('selected', slug=selection.slug, date=selection.date,
                        sensitivity=selection.sensitivity, separation=selection.separation,
                        gb=round(selection.total_mb / 1024, 2))
      selections += chosen
  finally:
    selector.__exit__(None, None, None)

  print(f"\n{len(selections)} run(s) selected "
        f"({sum(s.total_mb for s in selections) / 1024:.2f} GB of archive files)")
  downloaded = []
  for index, selection in enumerate(selections, 1):
    print(f"\n[{index}/{len(selections)}] download {selection.name}: {selection.label}")
    try:
      download(selection, log=print)
      downloaded.append(selection)
    except Exception as exc:
      print(f"  !! download failed: {exc}")
      _selection_failed(sweep, oversight, selection, exc)
      skipped.append(f"{selection.name}: {selection.label}")
  return downloaded, skipped


def _print_table(selections):
  print(f"  {len(selections)} observation(s):")
  for index, s in enumerate(selections, 1):
    print(f"  {index:>3}. {s.label:<24} {s.config + '-config':<10} {s.date:<10} "
          f"{s.sensitivity:<12} {s.separation:<7} {s.archive_name}")


def _selection_failed(sweep, oversight, selection, exc):
  result = runner.RunResult(selection=selection, run_dir=Path('(not created)'),
                            status='setup-error', detail=f"{type(exc).__name__}: {exc}")
  capture(result, sweep, oversight, error=exc)


def capture(result, sweep, oversight, error=None):
  """Record a failure, and never let the recording of one end the sweep."""
  try:
    failures.record(result, sweep.failed_dir, oversight, error=error)
  except Exception as exc:
    print(f"  !! could not capture the failure for {result.selection.name}: {exc!r}")
    oversight.event('failure', source=result.selection.name, status=result.status,
                    detail=result.detail, capture_error=repr(exc))


# -------------------------------------------------------------- pipeline phase
def run_one(selection, sweep, cores, oversight, dry_run=False, fresh=False):
  """Seed, run and tidy up one selection. Never raises: a failure is a result.

  Everything is caught here rather than at the pool, so one broken run cannot
  take its batch down with it -- the siblings keep going and the sweep proceeds
  to the next batch.
  """
  options, label = sweep.options, f"{selection.name}: {selection.label}"
  try:
    run_seed = seed.build(selection, sweep.preset.seed, options['source_name'])
    run_dir = runner.prepare(selection, sweep.runs_dir, run_seed, fresh=fresh)
  except Exception as exc:
    print(f"  !! {label}: could not prepare the run directory: {exc}")
    result = runner.RunResult(selection, sweep.runs_dir / selection.slug,
                              'setup-error', detail=f"{type(exc).__name__}: {exc}")
    oversight.event('run-end', slug=selection.slug, status=result.status, detail=result.detail)
    capture(result, sweep, oversight, error=exc)
    return result

  if dry_run:
    print(f"  .. {label}: seeded {run_dir} (dry run)")
    return runner.RunResult(selection, run_dir, 'skipped', detail='dry run')

  print(f"  >> {label}: starting in {run_dir}" + (f"  [cores {cores}]" if cores else ''))
  oversight.event('run-start', slug=selection.slug, cores=cores)
  try:
    result = runner.execute(selection, run_dir, cores=cores, timeout=options['timeout'],
                            attended=options['attended'])
  except Exception as exc:   #a bug in the harness must not take the batch with it
    print(f"  !! {label}: the harness itself failed: {exc!r}")
    result = runner.RunResult(selection, run_dir, 'setup-error',
                              detail=f"{type(exc).__name__}: {exc}")

  oversight.event('run-end', slug=selection.slug, status=result.status,
                  minutes=round(result.seconds / 60, 1), results=result.results_dir,
                  detail=result.detail)
  if result.ok:
    print(f"  OK {label}: {result.seconds / 60:.1f} min"
          + (f"  -> {result.results_dir}" if result.results_dir else ''))
    if options['cleanup']:
      runner.cleanup(run_dir)
  else:
    print(f"  !! {label}: {result.status} after {result.seconds / 60:.1f} min "
          f"-- {result.detail[:150]}")
    capture(result, sweep, oversight)
  return result


def run_batches(selections, sweep, oversight, dry_run=False, fresh=False):
  """Work through the selections in parallel batches (one at a time when attended)."""
  options = sweep.options
  size = 1 if options['attended'] else options['batch_size']
  slots = core_slots(options['cores'], size)
  results = []
  batches = [selections[i:i + size] for i in range(0, len(selections), size)]
  for number, batch in enumerate(batches, 1):
    print(f"\n=== Batch {number}/{len(batches)}: "
          f"{', '.join(s.slug for s in batch)} ===")
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(batch)) as pool:
      futures = [pool.submit(run_one, selection, sweep, slots[slot], oversight,
                             dry_run, fresh)
                 for slot, selection in enumerate(batch)]
      results += [future.result() for future in futures]
    print(f"=== Batch {number} finished in {(time.perf_counter() - started) / 60:.1f} min ===")
  return results


def parse_cores(spec):
  """'24-27,30' -> ['24','25','26','27','30']."""
  cores = []
  for part in str(spec).split(','):
    part = part.strip()
    if not part:
      continue
    if '-' in part:
      low, high = (int(x) for x in part.split('-', 1))
      cores += [str(c) for c in range(low, high + 1)]
    else:
      cores.append(str(int(part)))
  return cores


def core_slots(spec, batch_size):
  """One comma-separated core list per parallel slot, or None when unpinned.

  Cores divide as evenly as they can; with fewer cores than slots the leftover
  slots run unpinned rather than being forced to share a single core.
  """
  if not spec:
    return [None] * batch_size
  cores = parse_cores(spec)
  if not cores:
    return [None] * batch_size
  per = max(1, len(cores) // batch_size)
  slots = [cores[i * per:(i + 1) * per] for i in range(batch_size)]
  #anything left over from an uneven split joins the last pinned slot
  leftover = cores[batch_size * per:]
  if leftover and slots[batch_size - 1]:
    slots[batch_size - 1] += leftover
  return [','.join(slot) if slot else None for slot in slots]


# ------------------------------------------------------------------- reporting
STATUS_ORDER = ('passed', 'failed', 'no-results', 'timeout', 'setup-error', 'skipped')


def report(sweep, results, skipped, seconds):
  """Print the pass's summary and fold it into report.json.

  A resumed sweep re-runs only part of the list, so earlier passes' runs are kept
  and this pass's results replace theirs by slug.
  """
  runs = {}
  try:
    previous = json.loads(sweep.report_path.read_text())
    runs = {r['slug']: r for r in previous.get('runs', []) if 'slug' in r}
  except (OSError, json.JSONDecodeError):
    previous = {}
  for r in results:
    runs[r.selection.slug] = {
      'slug': r.selection.slug, 'source': r.selection.name,
      'proj_code': r.selection.proj_code, 'segment': r.selection.segment,
      'band': r.selection.band, 'date': r.selection.date,
      'sensitivity': r.selection.sensitivity, 'separation': r.selection.separation,
      'status': r.status, 'returncode': r.returncode, 'seconds': round(r.seconds, 1),
      'run_dir': str(r.run_dir), 'results_dir': r.results_dir, 'detail': r.detail,
    }
  not_run = sorted(set(previous.get('not_run', [])) | set(skipped))

  print('\n' + '=' * 72)
  print(f" {sweep.root.name}: pass finished in {seconds / 60:.1f} min "
        f"-- {len(results)} run(s) this pass, {len(skipped)} not run")
  print('=' * 72)
  for status in STATUS_ORDER:
    for r in results:
      if r.status != status:
        continue
      detail = r.detail[:110] + ('...' if len(r.detail) > 110 else '')
      print(f"  {status:<11} {r.selection.slug:<34} {r.seconds / 60:>6.1f} min"
            + (f"  {detail}" if detail else ''))
  for label in skipped:
    print(f"  {'not-run':<11} {label}")

  counts = {}
  for entry in runs.values():
    counts[entry['status']] = counts.get(entry['status'], 0) + 1
  summary = {
    'when': datetime.now().isoformat(timespec='seconds'),
    'harness': sweep.kind,
    'preset': sweep.preset.name,
    'targets': [t.label for t in sweep.targets],
    'options': sweep.options,
    'seconds_this_pass': round(seconds, 1),
    'counts': counts,
    'not_run': not_run,
    'runs': list(runs.values()),
  }
  sweep.report_path.write_text(json.dumps(summary, indent=2) + '\n')
  print(f"\n Oversight log: {sweep.root / 'oversight.log'}")
  print(f" Report:        {sweep.report_path}")
  if any(s not in ('passed', 'skipped') for s in counts):
    print(f" Failures:      {sweep.failed_dir}")
  return summary


def summarize(sweep, oversight=None):
  """The kind's sweep-wide products (a lightcurve plot, say), from every run that
  has passed so far. Never raises: the runs already have their verdicts."""
  hook = getattr(KINDS.get(sweep.kind), 'summarize', None)
  if hook is None:
    return None
  try:
    return hook(sweep)
  except Exception as exc:
    print(f"!! could not build the {sweep.kind} summary: {exc!r}")
    if oversight is not None:
      oversight.event('summary-failed', harness=sweep.kind, detail=repr(exc))
    return None


# ----------------------------------------------------------------------- entry
def execute(sweep, kind, dry_run=False, select_only=False, fresh=False):
  """Run a new sweep end to end. Returns the process exit status."""
  oversight = Oversight(sweep.root)
  oversight.event('sweep-start', harness=sweep.kind, preset=sweep.preset.name,
                  targets=len(sweep.targets), attended=sweep.options['attended'])
  started = time.perf_counter()
  selections, skipped = select(sweep, kind, oversight)
  write_manifest(selections, sweep.manifest)
  print(f"\nManifest: {sweep.manifest}  ({len(selections)} selected, {len(skipped)} not run)")
  if select_only:
    oversight.event('sweep-end', note='select-only')
    print('--select-only: stopping before the pipeline phase.')
    return 0
  return _finish(sweep, oversight, selections, skipped, started, dry_run, fresh)


def resume(sweep, dry_run=False, fresh=False):
  """Re-run every selection of an existing sweep that has not passed yet."""
  oversight = Oversight(sweep.root)
  done = {slug for slug, status in oversight.last_status().items() if status == 'passed'}
  selections = [s for s in read_manifest(sweep.manifest) if s.slug not in done]
  print(f"{sweep.root.name}: {len(done)} run(s) already passed, "
        f"{len(selections)} to run")
  oversight.event('sweep-resume', to_run=len(selections), passed=len(done))
  if not selections:
    oversight.event('sweep-end', note='nothing left to run')
    return 0
  return _finish(sweep, oversight, selections, [], time.perf_counter(), dry_run, fresh)


def _finish(sweep, oversight, selections, skipped, started, dry_run, fresh):
  if not selections:
    oversight.event('sweep-end', note='nothing to run')
    print('Nothing to run.')
    return 1
  try:
    results = run_batches(selections, sweep, oversight, dry_run, fresh)
  except KeyboardInterrupt:
    oversight.event('sweep-end', note='interrupted')
    print('\nInterrupted; resume with: run_harness.py resume ' + str(sweep.root))
    return 130
  summary = report(sweep, results, skipped, time.perf_counter() - started)
  if not dry_run:
    summarize(sweep, oversight)
  oversight.event('sweep-end', **summary['counts'])
  bad = sum(n for status, n in summary['counts'].items() if status not in ('passed', 'skipped'))
  return 1 if (bad or summary['not_run']) else 0
