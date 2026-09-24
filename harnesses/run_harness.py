#!/usr/bin/env python3
"""Run the pipeline over many observations, unattended and in parallel.

    ./run_harness.py full-auto "3C 15" "3C 31, AL0405"             # deepest obs of each
    ./run_harness.py full-auto --targets-file ../names.txt --preset full_auto_selfcal
    ./run_harness.py lightcurve "4C 35.03" --bands C               # every epoch < 100"
    ./run_harness.py lightcurve "4C 35.03" --preset lightcurve_deep  # interactive, attended
    ./run_harness.py resume sweeps/full-auto_full_auto_20260924-150000
    ./run_harness.py summarize sweeps/lightcurve_lightcurve_20260924-161811
    ./run_harness.py presets

A target is a source name, or 'name, PROJ' to hold it to a project. Settings come
from a preset (presets/<name>.json); any flag given here overrides the preset's
options. Every sweep gets its own folder under sweeps/. See HARNESS.md.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   #so 'harness' imports

from harness import presets                                # noqa: E402
from harness.kinds import KINDS                            # noqa: E402
from harness.pipeline import VENV_PYTHON                   # noqa: E402
from harness.selection import parse_target, read_targets   # noqa: E402
from harness.sweep import SWEEPS_DIR, Sweep                # noqa: E402
from harness import sweep as sweep_module                  # noqa: E402

#flag dest -> preset option. Defaults are None throughout: only a flag actually
#given overrides the preset.
RUN_OPTION_FLAGS = ('batch_size', 'cores', 'timeout', 'cleanup')
SELECTION_OPTION_FLAGS = ('bands', 'projects', 'before_year', 'max_gb', 'limit', 'source_name')


def _run_flags(parser):
  parser.add_argument('--batch-size', type=int, help='runs executed in parallel')
  parser.add_argument('--cores', help='CPU cores to confine the sweep to, e.g. "24-31"; '
                                      'split evenly across a batch')
  parser.add_argument('--timeout', type=int, help='seconds before a single run is killed')
  parser.add_argument('--no-cleanup', dest='cleanup', action='store_const', const=False,
                      help="keep a passed run's measurement sets and scratch")
  parser.add_argument('--dry-run', action='store_true',
                      help='seed each run directory but run nothing')
  parser.add_argument('--fresh', action='store_true',
                      help='wipe a run directory before running it')


def parse_args(argv=None):
  parser = argparse.ArgumentParser(description=(__doc__ or '').split('\n\n')[0],
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
  commands = parser.add_subparsers(dest='command', required=True)

  for kind in KINDS.values():
    sub = commands.add_parser(kind.NAME, help=kind.HELP)
    sub.add_argument('targets', nargs='*', metavar='TARGET',
                     help="a source, or 'source, PROJ' to hold it to a project")
    sub.add_argument('--targets-file', help='one target per line; # comments allowed')
    sub.add_argument('--preset', default=kind.DEFAULT_PRESET,
                     help=f'a preset name in presets/ or a path (default {kind.DEFAULT_PRESET})')
    sub.add_argument('--sweeps-dir', default=str(SWEEPS_DIR),
                     help='where the sweep folder is made')
    sub.add_argument('--select-only', action='store_true',
                     help='search and download only; write the manifest and stop')
    sub.add_argument('--bands', nargs='+', metavar='BAND', help='only these bands')
    sub.add_argument('--projects', nargs='+', metavar='PROJ',
                     help="only these projects, for targets that don't name their own")
    sub.add_argument('--before-year', type=int,
                     help='an observation counts as pre-EVLA when its year is below this')
    sub.add_argument('--max-gb', type=float, help='skip a segment bigger than this (0 = no cap)')
    sub.add_argument('--limit', type=int, help='at most N observations per target')
    sub.add_argument('--source-name', choices=('archive', 'input'),
                     help="'archive' names the target as the observation does; 'input' as you did")
    if 'all_obs' in kind.DEFAULT_OPTIONS:
      sub.add_argument('--all-obs', action='store_const', const=True,
                       help='run every runnable observation, not just the deepest')
    if 'max_sep_arcsec' in kind.DEFAULT_OPTIONS:
      sub.add_argument('--max-sep', dest='max_sep_arcsec', type=float,
                       help='keep observations pointed within this many arcsec')
    _run_flags(sub)
    sub.set_defaults(kind=kind)

  sub = commands.add_parser('resume', help="re-run a sweep's runs that have not passed")
  sub.add_argument('sweep_dir', help='the sweep folder')
  _run_flags(sub)

  sub = commands.add_parser('summarize', help="rebuild a sweep's summary (the lightcurve "
                                              "plot) from the runs that have passed")
  sub.add_argument('sweep_dir', help='the sweep folder')

  commands.add_parser('presets', help='list the presets and what they are for')
  return parser.parse_args(argv)


def list_presets():
  for preset, error in presets.available():
    if error:
      print(f"  {preset:<22} !! {error}")
    else:
      print(f"  {preset.name:<22} [{preset.harness}] {preset.label}")
  return 0


def gather_targets(args):
  targets = []
  if args.targets_file:
    targets += read_targets(args.targets_file)
  for text in args.targets:
    if target := parse_target(text):
      targets.append(target)
  return targets


def overrides(args, keys):
  return {k: getattr(args, k, None) for k in keys}


def check_attended(options):
  if options['attended'] and not os.environ.get('DISPLAY'):
    raise presets.PresetError('this preset is attended (interactive cleaning) and needs '
                              'a display, but DISPLAY is not set')


def main(argv=None):
  args = parse_args(argv)
  if args.command == 'presets':
    return list_presets()
  if not VENV_PYTHON.is_file():
    print(f"No pipeline interpreter at {VENV_PYTHON}. Run ./run.sh once to build "
          f"the virtual environment.", file=sys.stderr)
    return 2

  if args.command == 'summarize':
    try:
      sweep = Sweep.open(args.sweep_dir)
    except (ValueError, KeyError, OSError) as exc:
      print(f"error: cannot open {args.sweep_dir}: {exc}", file=sys.stderr)
      return 2
    if not hasattr(KINDS.get(sweep.kind), 'summarize'):
      print(f"error: the {sweep.kind} harness has no summary", file=sys.stderr)
      return 2
    return 0 if sweep_module.summarize(sweep) else 1

  if args.command == 'resume':
    try:
      sweep = Sweep.open(args.sweep_dir, overrides(args, RUN_OPTION_FLAGS))
      presets.validate(sweep.preset, sweep.options)
      check_attended(sweep.options)
    except (presets.PresetError, ValueError, KeyError, OSError) as exc:
      print(f"error: cannot resume {args.sweep_dir}: {exc}", file=sys.stderr)
      return 2
    return sweep_module.resume(sweep, dry_run=args.dry_run, fresh=args.fresh)

  try:
    kind = args.kind
    preset = presets.load(args.preset)
    if preset.harness != kind.NAME:
      raise presets.PresetError(f"preset {preset.name} is for the {preset.harness} "
                                f"harness, not {kind.NAME}")
    options = presets.resolve_options(
      kind.DEFAULT_OPTIONS, preset,
      overrides(args, RUN_OPTION_FLAGS + SELECTION_OPTION_FLAGS
                + tuple(kind.DEFAULT_OPTIONS)))
    presets.validate(preset, options)
    check_attended(options)
    targets = gather_targets(args)
  except (presets.PresetError, ValueError, OSError) as exc:
    print(f"error: {exc}", file=sys.stderr)
    return 2
  if not targets:
    print('error: give at least one target, or --targets-file', file=sys.stderr)
    return 2

  sweep = Sweep.create(args.sweeps_dir, kind.NAME, preset, options, targets)
  print(f"Sweep: {sweep.root}\n  {kind.NAME} with preset {preset.name}"
        f" ({preset.label}), {len(targets)} target(s)")
  return sweep_module.execute(sweep, kind, dry_run=args.dry_run,
                              select_only=args.select_only, fresh=args.fresh)


if __name__ == '__main__':
  sys.exit(main())
