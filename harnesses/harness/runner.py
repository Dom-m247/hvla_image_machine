"""One pipeline run, in its own working directory.

Almost every path the pipeline writes is relative to the working directory --
measurement_sets/, <name>_results/, the CASA logs, import.json itself -- so a
directory per run is what makes parallel runs safe. Nothing else needs isolating:
credentials, the calibrator table and the downloaded archives are all resolved
from the project root, and importvla only reads them.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import seed as seed_module
from .pipeline import MAIN_SCRIPT, MS_SUB_PATH, REPO_ROOT, VENV_PYTHON

#The captured stdout/stderr of a run. Deliberately not '*.log': cleanup.sh scrubs
#every .log outside a results folder, and this file has to survive that.
RUN_OUTPUT = 'harness_run.out'
CLEANUP_SCRIPT = REPO_ROOT / 'cleanup.sh'
DEFAULT_TIMEOUT = 4 * 60 * 60   #seconds; a classic-VLA reduction, generously


@dataclass
class RunResult:
  selection: object
  run_dir: Path
  status: str            #'passed' | 'failed' | 'no-results' | 'timeout' | 'setup-error'
  returncode: int | None = None
  seconds: float = 0.0
  detail: str = ''       #why it failed, when it did
  results_dir: str = ''  #the <proj>_<source>_<band>_results folder, when one was made

  @property
  def ok(self):
    return self.status == 'passed'


def prepare(selection, runs_root, seed, fresh=False):
  """Create the run directory and write `seed` (a seed.build dict) into it.

  An existing directory is reused unless `fresh`: importvla and the splits all
  skip work that is already on disk, so a resumed run picks up where the last
  one stopped instead of re-importing the archive.
  """
  run_dir = Path(runs_root) / selection.slug
  if fresh and run_dir.exists():
    shutil.rmtree(run_dir)
  run_dir.mkdir(parents=True, exist_ok=True)
  #importvla writes measurement_sets/<proj>_fullset.ms and will not create the parent
  (run_dir / MS_SUB_PATH.strip('/')).mkdir(exist_ok=True)
  seed_module.write(seed, run_dir)
  return run_dir


def command(cores=None):
  """The pipeline invocation, optionally pinned to a set of CPU cores.

  --importRun is what makes the run hands-free; --no-ms-tar drops the calibrated-MS
  tarball, which is the single largest artifact a run produces and is redundant
  here because the MS itself is deleted on success anyway.
  """
  argv = [str(VENV_PYTHON), str(MAIN_SCRIPT), '--importRun', '--no-ms-tar']
  if cores and shutil.which('taskset'):
    argv = ['taskset', '--cpu-list', cores] + argv
  return argv


def environment(cores=None, attended=False):
  """The child's environment: headless, and not oversubscribing the CPU.

  DISPLAY is removed rather than left alone -- every 'is there a display' check in
  the pipeline (the test-image viewer, the plotms flag review, the archive form)
  then takes its headless branch, and export_png brings its own Xvfb regardless.
  An attended run keeps it: interactive tclean needs somewhere to draw.
  """
  env = dict(os.environ)
  if not attended:
    env.pop('DISPLAY', None)
  threads = str(len(cores.split(',')) if cores else 1)
  env.update(OMP_NUM_THREADS=threads, OPENBLAS_NUM_THREADS=threads,
             MKL_NUM_THREADS=threads, NUMEXPR_NUM_THREADS=threads)
  return env


def execute(selection, run_dir, cores=None, timeout=DEFAULT_TIMEOUT, attended=False):
  """Run the pipeline in `run_dir` and return a RunResult.

  stdin is /dev/null on purpose. --importRun should never prompt, but a prompt
  that slips through has to fail the run rather than hang the whole sweep: with
  no stdin, input() raises EOFError and the traceback names the call site.

  An attended run (interactive cleaning) is the exception: stdin stays on the
  terminal, output is teed to the terminal as well as the capture file, and
  there is no timeout -- a person drawing masks sets the pace.
  """
  run_dir = Path(run_dir)
  output = run_dir / RUN_OUTPUT
  started = time.perf_counter()
  #wall clock too: the verdict has to tell a results folder this run collected
  #from one an earlier run left behind in a reused directory
  launched = time.time()
  with open(output, 'w') as sink:
    sink.write(f"$ {' '.join(command(cores))}\n  (cwd {run_dir})\n\n")
    sink.flush()
    try:
      if attended:
        code = _run_attended(command(cores), run_dir, environment(cores, True), sink)
      else:
        completed = subprocess.run(
          command(cores), cwd=run_dir, env=environment(cores),
          stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT,
          timeout=timeout,
        )
        code = completed.returncode
    except subprocess.TimeoutExpired:
      sink.write(f"\n\n*** harness: killed after {timeout}s ***\n")
      return RunResult(selection, run_dir, 'timeout', None,
                       time.perf_counter() - started,
                       f"exceeded the {timeout}s per-run timeout")
    except Exception as exc:   #could not even start it: missing venv, bad cwd
      sink.write(f"\n\n*** harness: could not launch: {exc!r} ***\n")
      return RunResult(selection, run_dir, 'setup-error', None,
                       time.perf_counter() - started, repr(exc))

  seconds = time.perf_counter() - started
  collapse_progress(output)
  results_dir = find_results_dir(run_dir, since=launched)
  status, detail = _verdict(code, results_dir, output)
  return RunResult(selection, run_dir, status, code, seconds, detail,
                   str(results_dir or ''))


def _run_attended(argv, run_dir, env, sink):
  """Run with stdin on the terminal, copying output to both the terminal and sink."""
  process = subprocess.Popen(argv, cwd=run_dir, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
  assert process.stdout is not None

  def tee():
    #byte-wise, so a prompt with no trailing newline still reaches the terminal
    while chunk := process.stdout.read1(4096):
      sys.stdout.buffer.write(chunk)
      sys.stdout.buffer.flush()
      sink.write(chunk.decode(errors='replace'))
    sink.flush()

  reader = threading.Thread(target=tee, daemon=True)
  reader.start()
  code = process.wait()
  reader.join()
  return code


#a run's captured output is mostly LoadingAnimation redrawing itself four times a
#second; over a long import that is tens of thousands of carriage returns and it
#buries the lines that matter. Above this size the file is left alone rather than
#read into memory.
MAX_COLLAPSE_BYTES = 64 * 1024 * 1024


def collapse_progress(output):
  """Resolve carriage returns in a captured log, so it reads as it looked.

  The pipeline animates progress by rewriting one line with '\r'. Piped to a
  file that leaves every intermediate frame in place; keeping only the last
  segment of each line is what a terminal would have shown.
  """
  output = Path(output)
  try:
    if output.stat().st_size > MAX_COLLAPSE_BYTES:
      return False
    #newline='' or the carriage returns are translated away on the way in, and
    #there is nothing left to collapse
    with output.open('r', errors='replace', newline='') as handle:
      text = handle.read()
  except OSError:
    return False
  if '\r' not in text:
    return True
  lines = [line.split('\r')[-1]
           for line in text.replace('\r\n', '\n').split('\n')]
  with output.open('w', newline='\n') as handle:
    handle.write('\n'.join(lines))
  return True


def _verdict(code, results_dir, output):
  """(status, detail) for a finished run.

  A zero exit is not on its own proof of success. The pipeline bails out of
  several dead ends with a bare sys.exit(), which leaves the status code at 0 --
  convert_to_ms does exactly that when importvla raises. A run that produced no
  results folder did not image anything, whatever it exited with.
  """
  if code != 0:
    return 'failed', f"pipeline exited {code}: {last_error(output)}"
  if results_dir is None:
    return 'no-results', ("pipeline exited 0 but collected no results folder: "
                          f"{last_error(output)}")
  return 'passed', ''


def last_error(output, lines=40, width=240):
  """A one-line summary of why a run failed, from the tail of its output.

  The pipeline's own failures print a recognisable line (a raised exception, a
  CASA SEVERE); anything else falls back to the last non-empty line. CASA's
  four-field log prefix is stripped -- it is a timestamp, a severity and an
  origin, none of which say what went wrong.
  """
  try:
    tail = [line.rstrip() for line in Path(output).read_text(
      errors='replace').splitlines()[-lines:] if line.strip()]
  except OSError:
    return '(no output captured)'
  if not tail:
    return '(no output captured)'
  for line in reversed(tail):
    if any(marker in line for marker in
           ('Error', 'error', 'Exception', 'SEVERE', 'Traceback', 'failed')):
      return _trim(line, width)
  return _trim(tail[-1], width)


def _trim(line, width):
  """One log line as a readable sentence: no CASA prefix, no runaway length."""
  parts = line.split('\t')
  #'<date time>\t<SEVERITY>\t<origin>\t<message>' -- keep only the message
  if len(parts) >= 4 and parts[1].strip().isupper():
    line = '\t'.join(parts[3:])
  line = ' '.join(line.split())
  return line[:width] + ('...' if len(line) > width else '')


def find_results_dir(run_dir, since=None):
  """The <proj>_<source>_<band>_results folder a run collected, if it got that far.

  `since` (a wall-clock time) discards a folder older than it. Run directories
  are reused by default, so without that check a run that died during import
  would inherit the previous pass's results folder and be scored as a success.
  collect_results copies into the folder, which moves its mtime.
  """
  found = sorted(Path(run_dir).glob('*_results'))
  if since is None:
    return next(iter(found), None)
  #a second of slack: mtime granularity, not a real age difference
  return next((d for d in found if d.stat().st_mtime >= since - 1), None)


def cleanup(run_dir, log=print):
  """Drop a successful run's scratch, keeping its results folder.

  Delegates to the project's own cleanup.sh so the harness scrubs exactly what a
  user's cleanup does -- MS directories, caltables, imaging products, logs and
  listobs -- and keeps prunng *_results/ for free. Best-effort: a sweep must not
  fail because the tidy-up did.
  """
  if not CLEANUP_SCRIPT.is_file():
    log(f"  cleanup skipped: {CLEANUP_SCRIPT} not found")
    return False
  try:
    subprocess.run(['bash', str(CLEANUP_SCRIPT)], cwd=run_dir,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=600, check=False)
    return True
  except Exception as exc:
    log(f"  cleanup failed in {run_dir}: {exc!r}")
    return False
