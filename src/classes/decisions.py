"""Mid-run user decisions: the one place the pipeline asks a question.

Every decision point routes through here rather than calling input() itself, so the
planned GUI prompt surface is a single swap instead of an edit per call site. Today
every prompt is a terminal prompt.

A recorded answer (from import.json) pre-empts the prompt entirely -- see resolved():
an imported run must replay hands-free, never re-asking what it already knows.
"""
from typing import Any, Callable, Sequence, TypeVar

from classes.constants import DECISIONS, AUTO
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
    """False when the run must not block on a person (an imported replay)."""
    return not getattr(getattr(options, 'sysArgs', None), 'importRun', False)


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
