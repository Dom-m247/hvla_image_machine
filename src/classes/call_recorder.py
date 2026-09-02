"""Records the CASA task calls a run makes, then emits a standalone `replay.py`.

The replay script is the run's decisions *flattened*: the exact, ordered CASA
task calls that executed, every parameter resolved to a literal -- no options,
no loops, no decision logic. Re-running it reproduces the process, given the
same input MS and CASA version.

    call_recorder.start()              # monkeypatch the recorded tasks, at startup
    ... run the pipeline ...
    call_recorder.write_replay(path)   # dump replay.py

Every module calls tasks as `ct.<task>(...)`, looked up on the shared casatasks
module at call time, so patching the module attributes intercepts all callers
without touching any call site.
"""
import sys
import subprocess
import datetime
from pathlib import Path
from typing import Any

import casatasks as ct

#Data-transforming / product-producing tasks the pipeline drives. imstat is omitted on
#purpose: it only measures (it drives the pipeline's decisions, but the replay has no
#decisions to drive, so recording it would just add noise).
_RECORDED_TASKS = (
  'importvla', 'listobs', 'flagdata', 'flagmanager', 'setjy', 'gaincal', 'bandpass',
  'fluxscale', 'applycal', 'blcal', 'split', 'tclean', 'impbcor', 'exportfits',
  'uvsub',
  'rmtables', 'delmod',
)

_calls: list[str] = []       #formatted "ct.task(...)" strings, in call order
_originals: dict = {}         #task name -> original function (for stop())
_active = False


def start():
  """Monkeypatch the recorded casatasks so each call is logged, then executed."""
  global _active
  if _active:
    return
  for name in _RECORDED_TASKS:
    orig = getattr(ct, name, None)
    if orig is None:
      continue
    _originals[name] = orig
    setattr(ct, name, _make_wrapper(name, orig))
  _active = True


def stop():
  """Restore the original (unrecorded) tasks."""
  global _active
  for name, orig in _originals.items():
    setattr(ct, name, orig)
  _originals.clear()
  _active = False


def _make_wrapper(name, orig):
  formatter = _format_tclean if name == 'tclean' else None

  def wrapper(*args, **kwargs):
    _calls.append(formatter(args, kwargs) if formatter else _format_call(name, args, kwargs))
    return orig(*args, **kwargs)  #real call is unchanged -- only the recorded string differs
  wrapper.__name__ = name
  wrapper.__doc__ = getattr(orig, '__doc__', None)
  return wrapper


def _format_call(name, args, kwargs):
  parts = [repr(a) for a in args]
  parts += [f"{k}={v!r}" for k, v in kwargs.items()]
  return f"ct.{name}({', '.join(parts)})"


def _format_tclean(args, kwargs):
  """Emit a *hands-free* replay of a tclean call.

  The live call may be interactive (user draws the mask) and, on the first cycle,
  carries no mask= at all -- the mask is only written to <imagename>.mask during the
  call. So for replay we: force interactive=False, and (when the call actually used a
  mask -- interactive drawing, auto-multithresh, or a supplied mask) point it at the
  concrete <imagename>.mask the call produced. That reproduces the exact regions with
  no human, regardless of how the mask originated. Calls that used no mask (e.g. a
  niter=0 dirty image, which writes no .mask) are left mask-free."""
  kw = dict(kwargs)
  replay = dict(kw)
  imagename = kw.get('imagename')
  used_mask = bool(kw.get('interactive')) or 'usemask' in kw or 'mask' in kw
  if imagename and used_mask:
    replay['usemask'] = 'user'
    replay['mask'] = f"{imagename}.mask"
  was_interactive = bool(kw.get('interactive'))
  replay['interactive'] = False
  line = _format_call('tclean', args, replay)
  if was_interactive:
    line += '  # replayed non-interactively from the saved mask'
  return line


def _version(modname):
  """Best-effort version string for a CASA module."""
  try:
    mod = __import__(modname)
    for attr in ('version_string', 'version'):
      fn = getattr(mod, attr, None)
      if callable(fn):
        val: Any = fn()
        return val if isinstance(val, str) else '.'.join(str(x) for x in val)
    return str(getattr(mod, '__version__', '?'))
  except Exception:
    return '?'


def _git_commit():
  try:
    return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'],
                                   stderr=subprocess.DEVNULL, text=True).strip()
  except Exception:
    return '?'


def provenance():
  """What pins this run's environment: timestamp, interpreter, CASA versions, commit.
  Shared by replay.py's header and the run log, so the two can never disagree."""
  return {
    'generated': datetime.datetime.now().isoformat(timespec='seconds'),
    'python': sys.version.split()[0],
    'casatasks': _version('casatasks'),
    'casatools': _version('casatools'),
    'git_commit': _git_commit(),
  }


def write_replay(path):
  """Write the recorded calls as a runnable replay.py at `path`, with a provenance
  header (versions + git commit) so the run's environment is pinned alongside it."""
  info = provenance()
  header = [
    '"""Auto-generated replay script.',
    '',
    'The exact CASA task calls this run executed, parameters resolved to literals.',
    'Re-running reproduces the process (assumes the same input MS and CASA version).',
    '',
    f"generated : {info['generated']}",
    f"python    : {info['python']}",
    f"casatasks : {info['casatasks']}    casatools: {info['casatools']}",
    f"git commit: {info['git_commit']}",
    '"""',
    'import casatasks as ct',
    '',
  ]
  body = _calls if _calls else ['# (no CASA task calls were recorded)']
  path = Path(path)
  path.write_text('\n'.join(header + body) + '\n')
  return str(path)
