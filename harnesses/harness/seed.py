"""The import.json a harness run is driven by.

--importRun is the pipeline's only hands-free mode: classes.decisions.is_interactive
is False for the whole run, so every mid-run prompt (calibrator pickers, flagging
review, self-cal steps, RMS region, test-image loop) resolves itself instead of
blocking. The harness therefore drives the pipeline the same way a user replaying
a saved run does -- it just writes the recipe first.
"""
import json
from pathlib import Path

from .pipeline import (
  AUTO, CLEAN_ROBUST, DECISIONS, DEFAULT_IMAGE_SIZE, FLAG_METHODS_DEFAULT,
  IMPORT_JSON, MIN_SNR, OFF, Options, delocalize,
)

#Filled from the selected observation, never from a preset: a preset that set
#one would point every run of a sweep at the same data.
OBSERVATION_KEYS = ('source', 'archive_file', 'archive_files', 'band', 'proj_code',
                    'search_alias', 'source_ra', 'source_decl', 'redshift')
#What a preset's "seed" may set: everything import.json round-trips, plus the two
#keys generate_dict appends conditionally, minus what comes from the observation
SEED_KEYS = tuple(k for k in Options.IMPORT_FIELDS + ('cell_size', 'self_cal_cycles')
                  if k not in OBSERVATION_KEYS)

#The unattended baseline a preset's "seed" is layered over: every stage that can
#decide for itself does, and the opt-in stages stay off.
BASE_DECISIONS = {'flux_cal': AUTO, 'phase_cal': AUTO, 'refant': AUTO,
                  'flagging': AUTO, 'self_cal': OFF, 'baseline_cal': OFF,
                  'core_subtract': OFF}


def build(selection, overrides=None, source_name='archive'):
  """The import.json dict for one selection, with a preset's overrides applied.

  `source_name` picks what goes in the 'source' field: 'archive' uses the Name
  column of the chosen observation -- the archive's own name for the target, so
  it matches listobs on the first try -- and 'input' uses the name as listed,
  which reads better but leans on SIMBAD alias matching to find the field.
  """
  paths = [delocalize(p) for p in selection.archive_files]
  if not paths:
    raise ValueError(f"{selection.name}: no archive files to run on")

  seed = {
    #--- what to reduce -------------------------------------------------------
    'source': selection.archive_name if source_name == 'archive' else selection.name,
    'archive_file': paths[0],
    'archive_files': paths,
    'band': selection.band,
    'proj_code': selection.proj_code,
    #NED-derived fields. IMPORT_FIELDS omits these on export, but
    #process_input_dict reads them back when present -- and it does not re-derive
    #them, so an import without them has an empty search_alias and no SIMBAD
    #aliases to fall back on when the target's name misses in listobs.
    'search_alias': selection.alias,
    'source_ra': selection.ra,
    'source_decl': selection.decl,
    'redshift': selection.redshift,
    **recipe(overrides),
  }
  _check(seed)
  return seed


def recipe(overrides=None):
  """Everything in a seed that is not the observation: the defaults with a preset's
  "seed" applied. Its 'decisions' merge key by key into the baseline; every other
  key replaces the default outright."""
  seed = {
    #--- what to decide, and how ---------------------------------------------
    'decisions': dict(BASE_DECISIONS),
    'reference_antenna': AUTO,
    'flagging_methods': list(FLAG_METHODS_DEFAULT),
    'min_snr': MIN_SNR,
    #no recorded answers: every stage resolves itself from the data
    'flux_cal_name': '', 'flux_cal_manual': None, 'phase_cal_name': '',
    'flag_selection': None, 'self_cal_plan': [],
    'self_cal_ap': None, 'self_cal_blcal': None,
    #'' leaves the off-source RMS to the automatic four-corner median, which is
    #what measure_off_source_rms falls back to when there is nobody to ask
    'rms_region': '',

    #--- imaging --------------------------------------------------------------
    'image_filename': None,        #auto-generated as <proj>_<source>_<band>
    'image_size': list(DEFAULT_IMAGE_SIZE),
    'interactive_image': False,    #tclean must not open a window and wait
    'use_custom_cell_size': False, #let find_cell_size size it from band + config
    'deconvolver': 'mtmfs',
    'weighting': 'briggs',
    'robust': CLEAN_ROBUST,
    'test_image': False,
    'mask': '',
  }
  for key, value in (overrides or {}).items():
    if key == 'decisions':
      seed['decisions'].update(value)
    else:
      seed[key] = value
  return seed


def check_recipe(overrides):
  """Raise ValueError if a preset's "seed" could not make a valid import.json."""
  _check({**dict.fromkeys(OBSERVATION_KEYS, ''), **recipe(overrides)})


#Keys Options.process_input_dict reads with [] rather than .get(): a missing one
#is a KeyError that exits the pipeline before it prints anything useful.
REQUIRED = ('source', 'archive_file', 'band', 'decisions', 'reference_antenna',
            'min_snr', 'image_filename', 'image_size', 'interactive_image',
            'use_custom_cell_size', 'deconvolver', 'weighting')


def _check(seed):
  missing = [k for k in REQUIRED if k not in seed]
  if missing:
    raise ValueError(f"seed is missing required key(s): {', '.join(missing)}")
  unknown = set(seed['decisions']) - set(DECISIONS)
  if unknown:
    raise ValueError(f"unknown decision point(s): {', '.join(sorted(unknown))}")
  bad = {k: v for k, v in seed['decisions'].items() if v not in DECISIONS[k]['modes']}
  if bad:
    raise ValueError('invalid decision mode(s): ' + ', '.join(
      f"{k}={v!r} (one of {', '.join(DECISIONS[k]['modes'])})" for k, v in bad.items()))
  if seed['use_custom_cell_size'] and not seed.get('cell_size'):
    raise ValueError("use_custom_cell_size is set but no cell_size was given")
  #process_input_dict reads self_cal_cycles with [] whenever self-cal is on
  if seed['decisions'].get('self_cal', OFF) != OFF and 'self_cal_cycles' not in seed:
    raise ValueError("self_cal is on but no self_cal_cycles was given")


def write(seed, run_dir):
  """Write the seed as the run directory's import.json, keeping a pristine copy.

  A successful run overwrites import.json with its own resolved recipe (every
  calibrator, region and self-cal parameter it settled on), which is the more
  useful artifact -- so the copy is what preserves what the harness actually
  asked for.
  """
  run_dir = Path(run_dir)
  text = json.dumps(seed, indent=4) + '\n'
  #IMPORT_JSON is the name import_settings.import_options opens, relative to the
  #working directory -- which is this run directory
  (run_dir / IMPORT_JSON).write_text(text)
  (run_dir / 'harness_seed.json').write_text(text)
  return run_dir / IMPORT_JSON
