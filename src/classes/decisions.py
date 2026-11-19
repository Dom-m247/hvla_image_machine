"""Mid-run user decisions: the one place the pipeline asks a question.

Every decision point routes through here rather than calling input() itself, so the
planned GUI prompt surface is a single swap instead of an edit per call site. Today
every prompt is a terminal prompt.

A recorded answer (from import.json) pre-empts the prompt entirely -- see resolved():
an imported run must replay hands-free, never re-asking what it already knows.
"""
import os
import sys
from typing import Any, Callable, Sequence, TypeVar

from classes.constants import DECISIONS, AUTO, OFF, VERIFY, EXPERIMENTAL_BANDS
from classes import run_log

T = TypeVar('T')
#The terminal surface itself lives in CLI_input, imported lazily inside each prompt:
#it pulls in options_class, which imports source_class, which imports this module.


def mode(options, name) -> str:
    """The chosen mode for decision `name`, or the registry default."""
    default = DECISIONS[name]['default']
    return (getattr(options, 'decisions', None) or {}).get(name, default)


def resolved(options, name):
    """A value recorded by an earlier run, or None. Pre-empts prompting so an
    imported run replays hands-free. '' counts as not recorded."""
    return getattr(options, name, None) or None


def is_interactive(options) -> bool:
    """False when the run must not block on a person (an imported replay). A run that
    require_attended let through is the exception: it has a person at it even under
    --importRun (the attended harness), so it asks."""
    if getattr(options, 'attended', False):
        return True
    return not getattr(getattr(options, 'sysArgs', None), 'importRun', False)


def why_unattended() -> str:
    """What keeps a person from taking part in this run, or '' when one can: the
    clean-mask viewer and plotms need a display, the prompts a terminal on stdin."""
    missing = []
    if not os.environ.get('DISPLAY'):
        missing.append('no DISPLAY')
    if not (sys.stdin and sys.stdin.isatty()):
        missing.append('no terminal on stdin')
    return ' and '.join(missing)


def require_attended(options):
    """An experimental band (EXPERIMENTAL_BANDS) runs only with a person at it.

    Without one -- an unattended harness run, a piped or remote replay -- the run stops
    here, before anything is calibrated. With one, the run shows them what matters:
    cleaning is interactive (they draw the masks), and automatic flagging becomes
    'verify', so they keep or revert the flags after the plotms check instead of the
    run accepting them unseen. Called again once the band is derived; acts once."""
    band = getattr(options, 'band', '')
    if band not in EXPERIMENTAL_BANDS or getattr(options, 'attended', False):
        return
    if missing := why_unattended():
        sys.exit(f"Stopping: {band} band is experimental and runs only attended, at a display "
                 f"and a terminal (the GUI, --cli, or the harness's lightcurve_deep preset), "
                 f"and this run has {missing}.")
    options.attended = True
    forced = []
    if not getattr(options, 'interactive_image', False):
        options.interactive_image = True
        forced.append('interactive cleaning (you draw the masks)')
    flagging = mode(options, 'flagging')
    if flagging == AUTO:
        options.decisions['flagging'] = VERIFY
        forced.append("flagging 'verify' (keep or revert the flags after the plotms check)")
    elif flagging == OFF:
        print(f"WARNING: flagging is off; {band}-band data are rarely free of RFI.")
        run_log.note('EXPERIMENTAL', 'Flagging', "OFF as requested -- nothing was reviewed")
    print('\n' + '*' * 78)
    print(f"*** EXPERIMENTAL: {band} BAND ***  unvetted: this run must stay attended.")
    if forced:
        print(f"Set for it: {'; '.join(forced)}.")
    print('*' * 78 + '\n')
    run_log.note('EXPERIMENTAL', 'Attended', 'display and terminal present; '
                 + ('; '.join(forced) if forced else 'interactive cleaning and flag review '
                                                    'were already chosen'))
    run_log.event(f"{band} band is experimental: attended run"
                  + (f"; set {'; '.join(forced)}" if forced else ''))


def announce(name, chosen, detail=''):
    """Record a decision's outcome to the run log and the terminal."""
    label = DECISIONS[name]['label']
    line = f"{label}: {chosen}" + (f" ({detail})" if detail else "")
    print(f"  {line}")
    run_log.event(line)


def confirm(label, detail='') -> bool:
    """Yes/no. Returns True on accept."""
    from classes.CLI_input import CLI
    if detail:
        print(detail)
    return CLI.getYesNo(label)


def pick(label, candidates: Sequence[T],
         formatter: Callable[[T], str] = str, default: int = 0) -> T | None:
    """Numbered picker over `candidates`; enter keeps the default. Returns the
    chosen item, or None when the list is empty."""
    from classes.CLI_input import CLI
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    idx = CLI.selectFromList(label, [formatter(c) for c in candidates], default)
    return candidates[idx]


def pick_many(label, candidates: Sequence[T], formatter: Callable[[T], str] = str,
              default: Sequence[int] | None = None) -> list:
    """Numbered multi-picker over `candidates`; enter keeps the default (all of them
    unless one is given). Returns the chosen items in candidate order."""
    from classes.CLI_input import CLI
    if not candidates:
        return []
    chosen = CLI.selectManyFromList(label, [formatter(c) for c in candidates], default)
    return [candidates[i] for i in chosen]


def value(label, current: T, cast: Callable[[str], Any] = str) -> T | Any:
    """Prompt for a replacement value; blank keeps `current`."""
    from classes.CLI_input import CLI
    return CLI.getValue(label, current, cast)
