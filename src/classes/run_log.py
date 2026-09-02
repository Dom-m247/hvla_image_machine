"""Human-readable run log -- what this run did, and why.

Two kinds of content: state read straight off Options at write() time, and
events recorded as they happen because they are gone by the end (per-cycle
self-cal scores, failure rates, flagging accept/revert).

Not machine-readable by design: import.json is the recipe, <name>.fit.json the
structured measurements. This is the one you read.

    run_log.start()                 # once, at startup
    run_log.event("...")            # as things happen
    run_log.write(options, path)    # render at the end
"""
import datetime
import time
from pathlib import Path

from classes import call_recorder

WIDTH = 80
LABEL = 21          #label column width, so values line up down the page
_MISSING = '(not recorded)'

_events: list[tuple[float, str]] = []     #(monotonic offset, text)
_cycles: list[dict] = []                  #self-cal cycle rows
_extra: dict[str, list[tuple[str, str]]] = {}   #section -> [(label, value)]
_timings: list[tuple[str, float]] = []
_start_time: float = 0.0


def start():
  """Begin a run log, clearing anything from a previous run in this process."""
  global _start_time
  _events.clear()
  _cycles.clear()
  _extra.clear()
  _timings.clear()
  _start_time = time.time()


def event(text):
  """Record a timestamped event -- something that happened and would otherwise
  only exist as a line of stdout."""
  _events.append((time.time() - _start_time if _start_time else 0.0, str(text)))


def cycle(label, solint='', calmode='', dynamic_range=None, change=None, decision=''):
  """Record one self-calibration cycle for the cycle table.

  This is the part of the run that cannot be reconstructed afterwards: only the
  best image survives on disk, so without this the reasoning that selected it
  (and the cycles that lost) is lost with it.
  """
  _cycles.append({'label': str(label), 'solint': str(solint), 'calmode': str(calmode),
                  'dr': dynamic_range, 'change': change, 'decision': str(decision)})


def note(section, label, value):
  """Attach an extra labelled value to a named section of the report."""
  _extra.setdefault(str(section), []).append((str(label), _text(value)))


def timing(label, seconds):
  """Record a stage duration (calibration, imaging, ...)."""
  _timings.append((str(label), float(seconds)))


def write(options, path):
  """Render the log to `path`. Returns the path written, or None on failure.

  Best-effort by design: a run that produced an image must never be failed by a
  problem formatting its report.
  """
  try:
    text = render(options)
  except Exception as exc:
    text = (f"HVLA Image Machine run log\n\nThe report could not be assembled: "
            f"{exc!r}\n\nRaw events follow.\n\n" + _event_lines())
  try:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return str(path)
  except Exception as exc:
    print(f"run_log: could not write {path}: {exc}")
    return None


def render(options):
  """Build the whole report as a string."""
  out = [_banner(), '']
  out += _header(options)
  out += _block('SOURCE', _source_rows(options))
  out += _block('OBSERVATION', _observation_rows(options))
  out += _block('CALIBRATION', _calibration_rows(options))
  out += _block('IMAGING', _imaging_rows(options))
  out += _cycle_table()
  out += _block('FINAL IMAGE', _final_image_rows(options))
  out += _block('OUTPUTS', _output_rows(options))
  out += _event_block()
  return "\n".join(out).rstrip() + "\n"


#--------------------------------------------------------------------- sections

def _header(options):
  info = call_recorder.provenance()
  rows = [
    ('Generated', info['generated']),
    ('Run mode', _run_mode(options)),
    ('Pipeline commit', info['git_commit']),
    ('CASA', f"casatasks {info['casatasks']}   casatools {info['casatools']}"),
    ('Python', info['python']),
  ]
  for label, seconds in _timings:
    rows.append((f"{label} time", _duration(seconds)))
  if _start_time:
    rows.append(('Total wall time', _duration(time.time() - _start_time)))
  return _rows(rows) + ['']


def _source_rows(options):
  source = _attr(options, 'source_ids')
  band = _get(options, 'band')
  rows = [
    ('Source', _get(options, 'source')),
    ('NED alias', _get(options, 'search_alias')),
    ('Name in listobs', _attr_of(source, 'listobs_name')),
    ('Field ID', _attr_of(source, 'field_id')),
    ('Source ID', _attr_of(source, 'source_id')),
    ('RA / Dec (listobs)', f"{_attr_of(source, 'ra')} / {_attr_of(source, 'decl')}"),
    ('RA / Dec (NED)', f"{_get(options, 'source_ra')} / {_get(options, 'source_decl')}"),
    ('Band', f"{band}   ({_band_origin(options)})"),
    ('Spectral windows', _get(options, 'spw_selection')),
  ]
  return rows + _extra.get('SOURCE', [])


def _observation_rows(options):
  data = _attr(options, 'observation_data')
  info = _attr_of_obj(data, 'obs_info')
  antennas = _attr_of_obj(data, 'antennas') or []
  archives = _get(options, 'archive_files') or _get(options, 'archive_file')
  rows = [
    ('Project code', _attr_of(info, 'project') or _get(options, 'proj_code')),
    ('Observer', _attr_of(info, 'observer')),
    ('Instrument', _attr_of(info, 'observtion')),   #sic: spelling in Obs_information
    ('Data records', _attr_of(info, 'data_records')),
    ('Antennas', len(antennas) if antennas else _MISSING),
    ('Array config', _config_origin(options, antennas)),
    ('Archive input', archives),
    ('Full MS', _ms(options, 'proj_name')),
    ('Calibration MS', _get(options, 'initial_calibration_filename')),
    ('Calibrated MS', _get(options, 'calibrated_filename')),
  ]
  return rows + _extra.get('OBSERVATION', [])


def _calibration_rows(options):
  amp, phase = _attr(options, 'flux_cal'), _attr(options, 'phase_cal')
  rows = [
    ('Flux calibrator', _calibrator(amp)),
    ('setjy model', _attr_of(amp, 'model')),
  ]
  if _get(options, 'target_is_phase_cal') is True:
    rows.append(('Phase calibrator', 'none -- the target serves as its own '
                 '(NED flux in band is above the floor)'))
  else:
    rows.append(('Phase calibrator', _calibrator(phase)))
  rows += [
    ('Selection method', _decision(options, 'phase_cal')),
    ('Reference antenna', _refant(options)),
    ('Minimum SNR', _get(options, 'min_snr')),
    ('Scan solint', _get(options, 'solint')),
  ]
  return rows + _extra.get('CALIBRATION', [])


def _imaging_rows(options):
  rows = [
    ('Deconvolver', _get(options, 'deconvolver')),
    ('Weighting', _get(options, 'weighting')),
    ('Cell size', _cell(options)),
    ('Image size', _image_size(options)),
    ('Masking', _masking(options)),
    ('Self-calibration', _self_cal(options)),
  ]
  return rows + _extra.get('IMAGING', [])


def _final_image_rows(options):
  fit = _get(options, 'fit_record')
  rows = [('Best image', _get(options, 'best_image_base'))]
  if not isinstance(fit, dict):
    rows.append(('Measurements', _MISSING + ' (no fit record on this run)'))
    return rows + _extra.get('FINAL IMAGE', [])
  beam = fit.get('beam') or {}
  rows += [
    ('Peak flux', _quantity(fit.get('peak_flux'))),
    ('Integrated flux', _quantity(fit.get('integrated_flux'))),
    ('Off-source RMS', f"{_number(fit.get('rms_jy_per_beam'), '.3e')} Jy/beam "
                       f"({fit.get('rms_method', '?')})"),
    ('Dynamic range', _number(fit.get('dynamic_range'), '.1f')),
    ('Restoring beam', _size(beam)),
    ('Frequency', f"{_number(fit.get('frequency_ghz'), '.6g')} GHz"),
    ('', ''),
    ('2D Gaussian fit', 'converged' if fit.get('converged') else 'DID NOT CONVERGE'),
    ('Fit box', fit.get('fit_box')),
    ('Fitted position', _position(fit.get('position'))),
    ('Convolved size', _size(fit.get('convolved_size'))),
    ('Deconvolved size', _size(fit.get('deconvolved_size'),
                               suffix=_resolved(fit))),
    ('Fit residual RMS', f"{_number(fit.get('residual_rms_jy_per_beam'), '.3e')} Jy/beam"),
  ]
  return rows + _extra.get('FINAL IMAGE', [])


def _output_rows(options):
  results = _get(options, 'results_dir')
  rows = [('Results folder', results)]
  try:
    for name in sorted(p.name for p in Path(str(results)).iterdir()):
      rows.append(('', name))
  except Exception:
    pass
  rows += [
    ('Clean mask', getattr(options, 'mask', '') or '(none)'),
    ('Reproduce with', 'import.json (recipe) + replay.py (exact CASA calls)'),
  ]
  return rows + _extra.get('OUTPUTS', [])


#----------------------------------------------------------------- cycle table

def _cycle_table():
  if not _cycles:
    return []
  out = [_rule('SELF-CALIBRATION CYCLES'), '']
  head = f"  {'cycle':<10} {'solint':<8} {'mode':<6} {'dyn.range':>10} {'change':>9}   decision"
  out += [head, '  ' + '-' * (len(head) - 2)]
  for row in _cycles:
    #a skipped cycle has no dynamic range; '-' keeps the column aligned where the
    #generic '(not recorded)' placeholder would blow the table apart
    dr = f"{row['dr']:.1f}" if isinstance(row['dr'], (int, float)) else '-'
    out.append(
      f"  {row['label']:<10} {row['solint'] or '-':<8} {row['calmode'] or '-':<6} "
      f"{dr:>10} {_change(row['change']):>9}   {row['decision']}")
  return out + ['']


def _change(value):
  if not isinstance(value, (int, float)):
    return '-'
  return f"{value:+.1f}%"


#--------------------------------------------------------------------- events

def _event_block():
  if not _events:
    return []
  return [_rule('EVENT LOG'), ''] + [f"  {line}" for line in _event_lines().splitlines()]


def _event_lines():
  return "\n".join(f"[{_duration(offset):>12}]  {text}" for offset, text in _events)


#--------------------------------------------------------------- value helpers

def _run_mode(options):
  args = _attr(options, 'sysArgs')
  if args is None:
    return _MISSING
  for flag, name in (('importRun', 'import (--importRun, from import.json)'),
                     ('radio_search', 'radio_search (--radio_search)'),
                     ('cliCalib', 'CLI calibration (--cliCalib)'),
                     ('cli', 'CLI (--cli)')):
    if getattr(args, flag, False):
      return name
  return 'GUI'


def _band_origin(options):
  """How the band was arrived at -- the user fixing it and the pipeline deriving
  it from the target's own spws are very different provenance.

  Note the raw getattr: _get() substitutes a placeholder string for a missing
  value, which is truthy, so testing _get() here would always take the first branch.
  """
  return ('resolved against the target\'s spectral windows'
          if getattr(options, 'spw_selection', '') else 'as configured')


def _config_origin(options, antennas):
  configured = _get(options, 'array_config')
  try:
    from data_calibration.parse_listobs import vla_config_from_antennas
    derived = vla_config_from_antennas(antennas)
  except Exception:
    derived = ''
  if derived:
    return f"{derived}   (derived from the antenna layout)"
  return f"{configured or _MISSING}   (not derivable from the antenna layout)"


def _calibrator(cal):
  if cal is None:
    return _MISSING
  name = _attr_of(cal, 'listobs_name') or _attr_of(cal, 'name')
  field = _attr_of(cal, 'field_id')
  return f"{name}   (field {field})"


def _refant(options):
  shown = _vla_names(_get(options, 'ref_ant'))
  requested = getattr(options, 'reference_antenna', '')   #raw: _get's placeholder is truthy
  #compare under VLA naming: a request for VA01 WAS honoured when the measurement
  #set calls that antenna EA01, and comparing raw spellings would report a
  #mismatch that never happened
  wanted = _vla_names(requested).lower()
  chosen_names = [name.strip().lower() for name in shown.split(',')]
  if (requested and str(requested).lower() not in ('auto', 'default', '')
      and wanted not in chosen_names):
    #surface the mismatch rather than hide it: a requested refant that did not end
    #up being used is exactly the kind of thing a run log exists to reveal
    return f"{shown}   (requested '{requested}')"
  return f"{shown}   (selected automatically)"


def _vla_names(value):
  """A refant string ('EA01,VA06') under VLA naming, for display."""
  text = _text(value)
  if text == _MISSING:
    return text
  try:
    from classes.observations_class import vla_antenna_name
  except Exception:
    return text
  return ','.join(vla_antenna_name(part) for part in text.split(','))


def _cell(options):
  size = _get(options, 'cell_size')
  if getattr(options, 'use_custom_cell_size', False):   #raw: _get's placeholder is truthy
    return f"{size}   (custom)"
  return f"{size}   (1/10 of the band/config angular resolution)"


def _image_size(options):
  size = getattr(options, 'image_size', None)
  if not isinstance(size, (list, tuple)) or len(size) < 2:
    return _text(size)
  return f"{size[0]} x {size[1]} pixels"


def _masking(options):
  """How the clean mask was arrived at.

  Careful: collect_results points options.mask at the mask THIS run saved into the
  results folder, so by write() time a mask path proves nothing about the input.
  A mask living outside the results folder is one that was supplied to the run;
  one inside it is this run's own output, and the mode is what actually applied.
  """
  mask = getattr(options, 'mask', '')
  results = str(getattr(options, 'results_dir', '') or '')
  if mask and not (results and str(mask).startswith(results)):
    return f"supplied mask reused: {mask}"
  return ('interactive (mask drawn by hand)' if getattr(options, 'interactive_image', None) is True
          else 'auto-multithresh (automatic)')


def _decision(options, name):
  """The mode chosen for a decision point, for display."""
  return (getattr(options, 'decisions', None) or {}).get(name, '-')


def _self_cal(options):
  mode = _decision(options, 'self_cal')
  if not getattr(options, 'do_self_cal', False):
    return 'disabled'
  return f"{mode}, {_get(options, 'self_cal_cycles')} cycle(s) requested"


def _ms(options, attr):
  name = _get(options, attr)
  if name in (None, '', _MISSING):
    return _MISSING
  try:
    from classes.constants import MS_SUB_PATH
    return f"{MS_SUB_PATH}{name}.ms"
  except Exception:
    return str(name)


def _quantity(quantity):
  if not isinstance(quantity, dict) or quantity.get('value') is None:
    return _MISSING
  text = f"{quantity['value']:.6g}"
  if quantity.get('error'):
    text += f" +/- {quantity['error']:.3g}"
  return f"{text} {quantity.get('unit') or ''}".strip()


def _size(size, suffix=''):
  if not isinstance(size, dict) or size.get('major_arcsec') is None:
    return _MISSING
  text = (f"{size['major_arcsec']:.4g} x {size['minor_arcsec']:.4g} arcsec "
          f"@ {_number(size.get('position_angle_deg'), '.4g')} deg")
  return f"{text}   ({suffix})" if suffix else text


def _resolved(fit):
  point = fit.get('is_point_source')
  if point is None:
    return ''
  return 'point source' if point else 'resolved'


def _position(position):
  if not isinstance(position, dict):
    return _MISSING
  if position.get('ra'):
    return f"{position['ra']} {position.get('dec', '')} ({position.get('frame', '')})".strip()
  return _MISSING


def _number(value, fmt='.6g'):
  return format(value, fmt) if isinstance(value, (int, float)) else _MISSING


def _duration(seconds):
  try:
    seconds = float(seconds)
  except (TypeError, ValueError):
    return _MISSING
  return str(datetime.timedelta(seconds=round(seconds)))


def _text(value):
  if value is None or value == '':
    return _MISSING
  return str(value)


#---------------------------------------------------------------- attr helpers
#Options members are populated across the whole run, and a run that failed part
#way still deserves a log -- so every read tolerates a missing/None attribute.

def _get(options, attr, default=_MISSING):
  """A value for DISPLAY -- substitutes a placeholder when absent.

  That placeholder is a non-empty string and therefore truthy, so never branch on
  the result of this (`if _get(o, 'flag'):` is always true). Use a raw getattr for
  anything you intend to test.
  """
  value = getattr(options, attr, None)
  return default if value is None or value == '' else value


def _attr(options, attr):
  return getattr(options, attr, None)


def _attr_of(obj, attr):
  if obj is None:
    return _MISSING
  return _text(getattr(obj, attr, None))


def _attr_of_obj(obj, attr):
  return getattr(obj, attr, None) if obj is not None else None


#------------------------------------------------------------------ formatting

def _banner():
  title = ' HVLA Image Machine -- run log '
  pad = (WIDTH - len(title)) // 2
  return "\n".join(['*' * WIDTH, '*' * pad + title + '*' * (WIDTH - pad - len(title)),
                    '*' * WIDTH])


def _rule(title):
  return "\n".join(['=' * WIDTH, f" {title}", '=' * WIDTH])


def _block(title, rows):
  return [_rule(title), ''] + _rows(rows) + ['']


def _rows(rows):
  out = []
  for label, value in rows:
    if not label and not value:
      out.append('')
    elif not label:
      out.append(f"  {' ' * LABEL}  {_text(value)}")
    else:
      out.append(f"  {label:<{LABEL}}: {_text(value)}")
  return out
