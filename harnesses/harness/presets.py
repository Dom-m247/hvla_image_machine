"""Named, editable settings for a sweep: harnesses/presets/<name>.json.

A preset has two halves. "options" are the harness's own knobs (batch size,
bands, the pre-EVLA cutoff...), which any command-line flag overrides. "seed" is
the import.json recipe every run of the sweep is driven by, layered over
seed.recipe()'s defaults. Everything is checked here, when the preset loads, so
a typo fails the sweep before the first network call rather than every run of it.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import runner, seed
from .pipeline import AUTO, FORCE, OFF, PRE_EVLA_YEAR

PRESETS_DIR = Path(__file__).resolve().parent.parent / 'presets'

#The knobs every harness kind understands. A kind adds its own (kinds/*.py
#DEFAULT_OPTIONS); a preset or a flag naming anything else is an error.
COMMON_OPTIONS = {
  'batch_size': 4,          #runs in parallel; batches run one after another
  'cores': None,            #'24-31' pins the sweep to those cores, split across a batch
  'timeout': runner.DEFAULT_TIMEOUT,
  'bands': [],              #only these bands
  'projects': [],           #only these project codes (a target's own list wins)
  'before_year': PRE_EVLA_YEAR,
  'max_gb': 20.0,           #skip a segment bigger than this (0 = no cap)
  'limit': 0,               #at most N observations per target (0 = all)
  'source_name': 'archive', #'archive' or 'input'; see seed.build
  'cleanup': True,          #run cleanup.sh in a passed run's directory
  'attended': False,        #a person is at the terminal: one run at a time, stdin open
}

#Modes that decide without asking. The calibrator pickers do NOT consult
#decisions.is_interactive, so 'verify' / 'manual' / 'guided' reach
#CLI.selectFromList and die on the closed stdin of an unattended run.
UNATTENDED_MODES = (AUTO, OFF, FORCE)


class PresetError(ValueError):
  """A preset that cannot drive a sweep. Carries its own reason."""


@dataclass
class Preset:
  name: str
  path: Path
  harness: str
  label: str = ''
  options: dict = field(default_factory=dict)
  seed: dict = field(default_factory=dict)

  def to_dict(self):
    return {'name': self.name, 'path': str(self.path), 'harness': self.harness,
            'label': self.label, 'options': self.options, 'seed': self.seed}


def resolve(name_or_path):
  """presets/<name>.json when it exists, otherwise the argument as a path."""
  named = PRESETS_DIR / f"{name_or_path}.json"
  if named.is_file():
    return named
  path = Path(name_or_path)
  if path.is_file():
    return path
  raise PresetError(f"no preset {name_or_path!r} in {PRESETS_DIR} and no such file")


def load(name_or_path):
  path = resolve(name_or_path)
  try:
    data = json.loads(path.read_text())
  except json.JSONDecodeError as exc:
    raise PresetError(f"{path}: not valid JSON ({exc})") from None
  if not isinstance(data, dict) or not data.get('harness'):
    raise PresetError(f"{path}: a preset is an object with at least a \"harness\" key")
  unknown = set(data) - {'harness', 'label', 'options', 'seed'}
  if unknown:
    raise PresetError(f"{path}: unknown top-level key(s): {', '.join(sorted(unknown))}")
  return Preset(name=path.stem, path=path, harness=data['harness'],
                label=data.get('label', ''), options=dict(data.get('options') or {}),
                seed=dict(data.get('seed') or {}))


def available():
  """Every preset in PRESETS_DIR, as (preset, None) or (file stem, error)."""
  found = []
  for path in sorted(PRESETS_DIR.glob('*.json')):
    try:
      found.append((load(path), None))
    except PresetError as exc:
      found.append((path.stem, str(exc)))
  return found


def resolve_options(kind_defaults, preset, overrides):
  """COMMON_OPTIONS <- the kind's defaults <- the preset <- flags actually given."""
  known = {**COMMON_OPTIONS, **kind_defaults}
  for source, values in (('preset ' + preset.name, preset.options),
                         ('command line', overrides)):
    if unknown := set(values) - set(known):
      raise PresetError(f"{source}: unknown option(s) for this harness: "
                        f"{', '.join(sorted(unknown))}")
  return {**known, **preset.options,
          **{k: v for k, v in overrides.items() if v is not None}}


def validate(preset, options):
  """Raise PresetError unless the preset's seed can drive every run of the sweep."""
  where = f"preset {preset.name} ({preset.path})"
  if taken := [k for k in preset.seed if k in seed.OBSERVATION_KEYS]:
    raise PresetError(f"{where}: seed sets {', '.join(taken)}, which come from each "
                      f"selected observation and cannot be preset")
  if unknown := [k for k in preset.seed if k not in seed.SEED_KEYS]:
    raise PresetError(f"{where}: seed key(s) import.json does not have: "
                      f"{', '.join(unknown)}")
  try:
    seed.check_recipe(preset.seed)
  except ValueError as exc:
    raise PresetError(f"{where}: {exc}") from None

  recipe = seed.recipe(preset.seed)
  if not options['attended']:
    asks = {k: v for k, v in recipe['decisions'].items() if v not in UNATTENDED_MODES}
    if asks:
      raise PresetError(
        f"{where}: {', '.join(f'{k}={v}' for k, v in asks.items())} would prompt, and "
        f"an unattended run has no one to answer. Use {'/'.join(UNATTENDED_MODES)}, "
        f"or set options.attended")
    if recipe['interactive_image']:
      raise PresetError(f"{where}: interactive_image needs a person at the display; "
                        f"set options.attended")
  if options['source_name'] not in ('archive', 'input'):
    raise PresetError(f"{where}: source_name must be 'archive' or 'input'")
  if options['batch_size'] < 1:
    raise PresetError(f"{where}: batch_size must be at least 1")
