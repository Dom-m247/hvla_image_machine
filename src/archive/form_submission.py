
import json
import os
import urllib.parse
import webbrowser
from pathlib import Path

from classes import creds
from classes.constants import (ARRAY_CONFIGURATION, BAND_ANGULAR_RESOLUTION,
                               BAND_LARGEST_SCALE)


#============================================================== CREDENTIALS
#The form is access-restricted (fetching it anonymously returns 401 + a Google
#sign-in page), so its URL is read from the credentials file rather than
#hardcoded here. classes.creds owns where that file lives.

FORM_URL_KEY = 'archive_form_url'  #creds key holding the /viewform link


def form_url():
  """The bare /viewform URL for the archive submission form."""
  return creds.load((FORM_URL_KEY,))[FORM_URL_KEY].split('?')[0]


#============================================================== FORM FIELD MAP
#Field name -> Google Forms entry id, in the order the form asks them. Keyed by
#name, never by position; an unmapped field is skipped and left blank.
#Value rules: multiple choice needs the EXACT option text; checkboxes repeat the
#parameter; dates split into entry.<id>_year/_month/_day; file uploads cannot be
#prefilled at all. Ids come from the form's own pre-filled link -- regenerate it
#if the questions change.
ENTRY_IDS = {
  #--- who is submitting (user) ---
  'submitter_name':     '1063096774',
  #--- source identity ---
  'source_name':        '1134785223',
  'j2000_name':         '89529589',
  'ra':                 '1820529680',
  'dec':                '671414957',
  'redshift':           '765935568',
  'reason':             '111773943',   #user
  #--- observation ---
  'survey':             '1060453887',
  'band':               '1809684721',
  'configuration':      '252414632',
  'central_frequency':  '481625369',
  'project_code':       '45581784',
  'observation_date':   '66590163',
  'expected_resolution':'2088978939',
  'expected_las':       '1485772817',
  'expected_primary_beam': '1751044051',
  #--- measurements ---
  'beam_size':          '1524467668',
  'knots':              '1860168911',  #user
  'hotspots':           '515008302',   #user
  'lobe_emission':      '1521737780',  #user
  'final_rms':          '126240566',   #Jy/beam
  'core_flux':          '1405271332',  #Jy
  'total_flux':         '1467263419',  #Jy; NUMBER-validated, so digits only
  #--- provenance ---
  'casa_version':       '1410456187',
  'amp_calibrator':     '701607635',
  'phase_calibrator':   '793652933',
  'observation_bandwidth': '945587924',
  'details':            '1166773415',  #user
  #polarization (522756219), leakage (795485759) and the uploads: user, in browser
}

SURVEY = 'Historical VLA'  #exact option text



#============================================================== VALUE GATHERING

def gather_automatic(options):
  """Everything the pipeline already knows, keyed to match ENTRY_IDS.

  Reads Options and options.fit_record the way run_log does -- every access
  tolerates a missing attribute, because a run that limped to the end still
  deserves a partly-filled form.
  """
  fit = getattr(options, 'fit_record', None) or {}
  beam = fit.get('beam') or {}
  position = fit.get('position') or {}
  amp, phase = getattr(options, 'flux_cal', None), getattr(options, 'phase_cal', None)

  ra, dec = _coordinates(options, position)

  values = {
    'source_name':       getattr(options, 'source', ''),
    'j2000_name':        _j2000_name(options, position),
    'ra':                ra,
    'dec':               dec,
    'redshift':          _text(getattr(options, 'redshift', '')),
    'survey':            SURVEY,
    'band':              _band(options),
    'configuration':     _configuration(options),
    'central_frequency': _number(fit.get('frequency_ghz')),
    'project_code':      getattr(options, 'proj_code', ''),
    'observation_date':  observation_date(options),
    'expected_resolution':   _band_table(BAND_ANGULAR_RESOLUTION, options),
    'expected_las':          _band_table(BAND_LARGEST_SCALE, options),
    'expected_primary_beam': _primary_beam(fit),
    'observation_bandwidth': _bandwidth(options),
    'beam_size':         _beam_size(beam),
    'final_rms':         _jy(fit.get('rms_jy_per_beam')),
    'core_flux':         _jy(fit.get('peak_flux') or fit.get('peak_jy_per_beam')),
    'total_flux':        _decimal(_jy(fit.get('image_flux_jy')
                                      or fit.get('integrated_flux'))),
    'casa_version':      _casa_version(),
    'amp_calibrator':    _calibrator(amp),
    'phase_calibrator':  _phase_calibrator(options, phase),
  }

  return values


#============================================================== URL BUILDING

def build_prefill_url(values, base_url=None):
  """Build the prefilled /viewform URL from a {field name: value} dict.

  Fields with no entry id yet, and empty values, are skipped -- they simply come
  up blank on the form. A list value is emitted as repeated parameters, which is
  how Forms encodes a multi-answer checkbox question.
  """
  base = (base_url or form_url()).split('?')[0]
  params = [('usp', 'pp_url')]
  for name, value in values.items():
    entry = ENTRY_IDS.get(name)
    if not entry:
      continue  #not mapped yet, or not a form field
    for item in (value if isinstance(value, (list, tuple)) else [value]):
      text = _text(item)
      if text:
        params.append((f"entry.{entry}", text))
  return f"{base}?{urllib.parse.urlencode(params)}"


def unmapped_fields(values):
  """Field names carrying a value that has nowhere to go yet.

  Worth surfacing while ENTRY_IDS is still being filled in: silently dropping a
  measured value is exactly the failure this keyed design exists to prevent.
  """
  return sorted(name for name, value in values.items()
                if _text(value) and not ENTRY_IDS.get(name))


#============================================================== OPEN + RECORD

def open_form(url):
  """Open the prefilled form in the user's browser. True if a browser took it.

  Always prints the URL first. the printed link is then the actual delivery mechanism, not
  a fallback message.
  """
  print(f"\nArchive submission form:\n  {url}\n")
  if not os.environ.get('DISPLAY'):
    print("No DISPLAY -- copy the link above into a browser to review and submit.")
    return False
  try:
    return webbrowser.open(url)
  except Exception as exc:
    print(f"Could not open a browser ({exc!r}); use the link above.")
    return False


def write_prefill_link(options, url):
  """Save the prefilled URL into the results folder. Returns the path, or None.

  Keeps the submission recoverable if the user closes the tab, without re-running.
  """
  results = str(getattr(options, 'results_dir', '') or '')
  if not results:
    return None
  try:
    path = Path(results) / 'archive_submission_link.txt'
    path.write_text(url + "\n")
    return str(path)
  except Exception as exc:
    print(f"form_submission: could not write the link: {exc}")
    return None


class _ArchivedRun:
  """Stand-in for Options, rebuilt from a finished results folder.

  gather_automatic only ever reads attributes off Options, so a plain object
  carrying the same names is enough.
  """
  source = ''
  band = ''
  proj_code = ''
  array_config = ''
  source_ra = ''
  source_decl = ''
  redshift = ''
  flux_cal = None
  phase_cal = None
  target_is_phase_cal = None
  observation_data = None
  fit_record: dict = {}
  results_dir = ''


def prompt_for_folder():
  """Ask which results folder to archive. '' means 'this run, at the end'."""
  answer = input("\nResults folder to archive "
                 "(or press enter to archive this run when it finishes): ").strip()
  return answer


def archive_existing(folder):
  """Build a submission from an already-finished results folder.

  Recovers the measurements from <name>.fit.json and the observation from the
  saved listobs; re-queries NED for the coordinates, which are derived from the
  source name rather than stored. Returns the prefilled URL, or None.
  """
  path = Path(folder).expanduser()
  if not path.is_dir():
    print(f"Not a folder: {path}")
    return None
  run = _ArchivedRun()
  run.results_dir = str(path)
  name = _run_name(path)
  if name:
    run.proj_code, run.source, run.band = _split_run_name(name)
  _load_fit(run, path, name)
  _load_listobs(run, path, name)
  _load_run_log(run, path, name)
  _load_ned(run)
  return submit(run)


def _run_name(path):
  """The <proj>_<source>_<band> stem the folder's products are named with."""
  for pattern in ('*.fit.json', '*-listobs.txt', '*.fits'):
    for found in sorted(path.glob(pattern)):
      return found.name.split('.fit.json')[0].split('-listobs.txt')[0].removesuffix('.fits')
  return path.name.removesuffix('_results')


def _split_run_name(name):
  """'<proj>_<source>_<band>' -> the three parts, tolerating '_' in the source."""
  try:
    proj, rest = name.split('_', 1)
    source, band = rest.rsplit('_', 1)
    return proj, source, band
  except ValueError:
    return '', name, ''


def _load_fit(run, path, name):
  fit_file = path / f"{name}.fit.json"
  if not fit_file.is_file():
    print(f"archive: no fit record in {path}; measurements will be blank.")
    return
  try:
    run.fit_record = json.loads(fit_file.read_text())
  except Exception as exc:
    print(f"archive: could not read {fit_file.name}: {exc}")


def _load_listobs(run, path, name):
  listobs = path / f"{name}-listobs.txt"
  if not listobs.is_file():
    print(f"archive: no listobs in {path}; observation details will be blank.")
    return
  try:
    from data_calibration.parse_listobs import parseListObs
    run.observation_data = parseListObs.populate_Obs_data(listobs.read_text())
    run.proj_code = getattr(run.observation_data.obs_info, 'project', '') or run.proj_code
  except Exception as exc:
    print(f"archive: could not parse {listobs.name}: {exc}")


class _Calibrator:
  """Name-only stand-in for source_info, recovered from the run log."""

  def __init__(self, name):
    self.listobs_name = name
    self.name = name


def _load_run_log(run, path, name):
  """The calibrators, which nothing else in the results folder records.

  <name>.log carries them as 'Flux calibrator      : 0137+331   (field 2)'; the
  phase line instead reads 'none -- ...' when the target served as its own.
  """
  import re

  log = path / f"{name}.log"
  if not log.is_file():
    print(f"archive: no run log in {path}; the calibrators will be blank.")
    return
  try:
    lines = log.read_text().splitlines()
  except Exception as exc:
    print(f"archive: could not read {log.name}: {exc}")
    return
  for line in lines:
    label, sep, value = line.partition(':')
    if not sep:
      continue
    label, value = label.strip(), re.sub(r'\s*\(field .*\)$', '', value.strip())
    if label == 'Flux calibrator':
      run.flux_cal = _Calibrator(value)
    elif label == 'Phase calibrator':
      if value.startswith('none --'):
        run.target_is_phase_cal = True
      else:
        run.phase_cal = _Calibrator(value)


def _load_ned(run):
  """Coordinates and redshift, which the results folder does not store."""
  if not run.source:
    return
  try:
    from API_integrations.NED import NED_API
    result = NED_API.obj_exists(run.source)
    if result:
      run.source_ra = result['ra_decl']['ra']
      run.source_decl = result['ra_decl']['decl']
      run.redshift = result.get('redshift', '')
  except Exception as exc:
    print(f"archive: NED lookup failed for {run.source!r}: {exc}")


def submit(options):
  """Gather, build, open, record. Returns the prefilled URL, or None.

  Best-effort by the same rule as run_log.write: a run that produced an image
  must never be failed by a problem with its paperwork.
  """
  try:
    values = gather_automatic(options)
    missing = unmapped_fields(values)
    if missing:
      print(f"form_submission: no entry id yet for {', '.join(missing)} "
            f"-- these will be blank on the form (see ENTRY_IDS).")
    url = build_prefill_url(values)
  except Exception as exc:
    print(f"form_submission: could not build the submission ({exc!r}).")
    return None
  open_form(url)
  write_prefill_link(options, url)
  return url


#============================================================== value helpers

def _text(value):
  """A scalar as form text. Non-scalars render blank, never as a repr.

  gather_automatic flattens the fit record's {value, error, unit} quantities
  through _jy(), but build_prefill_url is callable on its own -- and a raw dict
  reaching a form field would be URL-encoded as its repr and submitted to the
  archive looking like data. A blank field is recoverable; a wrong one is not.
  """
  if value is None:
    return ''
  if isinstance(value, dict):
    print(f"form_submission: refusing to submit a raw {sorted(value)[:3]} dict "
          f"as form text -- flatten it first (see _jy / _beam_size).")
    return ''
  return str(value).strip()


def _number(value, fmt='.6g'):
  return format(value, fmt) if isinstance(value, (int, float)) else ''


def _decimal(text):
  """Plain decimal, for the number-validated questions.

  _number's '.6g' turns small fluxes into '7.3e-05', which a Forms number
  question may reject. Returns '' rather than a rejected value.
  """
  try:
    return f"{float(text):.9f}".rstrip('0').rstrip('.') or '0'
  except (TypeError, ValueError):
    return ''


def _casa_version():
  """CASA versions as recorded for the replay header, so the two agree."""
  from classes import call_recorder
  try:
    info = call_recorder.provenance()
    return f"casatasks {info['casatasks']}, casatools {info['casatools']}"
  except Exception:
    return ''


def _configuration(options):
  """VLA array config (A/B/C/D), derived from the antenna layout where possible."""
  data = getattr(options, 'observation_data', None)
  antennas = getattr(data, 'antennas', None) or []
  try:
    from data_calibration.parse_listobs import vla_config_from_antennas
    derived = vla_config_from_antennas(antennas)
  except Exception:
    derived = ''
  return derived or _text(getattr(options, 'array_config', ''))


def _config_index(options):
  """Column index (A/B/C/D) into the BAND_* tables, matching Cleaner's choice."""
  letter = _configuration(options).strip().upper()[:1]
  return {'A': 0, 'B': 1, 'C': 2, 'D': 3}.get(letter, ARRAY_CONFIGURATION)


def _band_table(table, options):
  """A band/config value from one of the BAND_* tables, in arcsec."""
  try:
    return f"{table[_band(options)][_config_index(options)]} arcsec"
  except (KeyError, IndexError, TypeError):
    return ''


def _primary_beam(fit):
  """VLA primary beam FWHM in arcmin: ~45/freq(GHz) for the 25 m dishes."""
  freq = fit.get('frequency_ghz')
  if not isinstance(freq, (int, float)) or freq <= 0:
    return ''
  return f"{45.0 / freq:.4g} arcmin"


def _bandwidth(options):
  """Total observed bandwidth in MHz, summed over the spectral windows."""
  data = getattr(options, 'observation_data', None)
  windows = getattr(data, 'spectral_windows', None) or []
  total = 0.0
  for window in windows:
    try:
      total += float(getattr(window, 'totbw_khz', 0) or 0)
    except (TypeError, ValueError):
      continue
  return f"{total / 1000.0:.6g} MHz" if total else ''


def _degrees(options, position):
  """(ra, dec) in degrees from the fit record, else from the NED lookup."""
  ra_deg, dec_deg = position.get('ra_deg'), position.get('dec_deg')
  if ra_deg is None or dec_deg is None:
    ra_deg = getattr(options, 'source_ra', None)
    dec_deg = getattr(options, 'source_decl', None)
  try:
    ra_deg, dec_deg = float(ra_deg), float(dec_deg)   # pyright: ignore[reportArgumentType]
  except (TypeError, ValueError):
    return None, None
  if not (0 <= ra_deg < 360 and -90 <= dec_deg <= 90):
    return None, None
  return ra_deg, dec_deg


def _sexagesimal(ra_deg, dec_deg):
  """Degrees -> (h, m, s, sign, d, m, s), with rounded seconds carried."""
  hours = ra_deg / 15.0
  hh = int(hours)
  mm = int((hours - hh) * 60)
  ss = ((hours - hh) * 60 - mm) * 60
  sign = '+' if dec_deg >= 0 else '-'
  dec_deg = abs(dec_deg)
  dd = int(dec_deg)
  am = int((dec_deg - dd) * 60)
  arcsec = ((dec_deg - dd) * 60 - am) * 60
  #rounding to 2dp can carry 59.996" up to 60"; borrow rather than emit ':60'
  if round(arcsec, 2) >= 60:
    arcsec, am = 0.0, am + 1
  if am == 60:
    am, dd = 0, dd + 1
  return hh, mm, ss, sign, dd, am, arcsec


def _coordinates(options, position):
  """(RA, Dec) as 'hh:mm:ss.ss' / 'dd:mm:ss.ss', the formats the form asks for.

  Always formatted from degrees, including when the fit record carries ready-made
  strings: those use astropy's precision, so passing them through would put two
  different formats in one field depending on which path filled it.
  """
  ra_deg, dec_deg = _degrees(options, position)
  if ra_deg is None or dec_deg is None:
    return '', ''
  hh, mm, ss, sign, dd, am, arcsec = _sexagesimal(ra_deg, dec_deg)
  return (f"{hh:02d}:{mm:02d}:{ss:05.2f}",
          f"{sign}{dd:02d}:{am:02d}:{arcsec:05.2f}")


def _j2000_name(options, position):
  """IAU J2000 designation, 8 digits: 'J0209+3547'.

  Truncated, not rounded -- IAU designations are built by truncating the
  coordinate, so this cannot reuse the rounded/carried sexagesimal above.
  """
  ra_deg, dec_deg = _degrees(options, position)
  if ra_deg is None or dec_deg is None:
    return ''
  hours = ra_deg / 15.0
  hh = int(hours)
  mm = int((hours - hh) * 60)
  sign = '+' if dec_deg >= 0 else '-'
  dec_deg = abs(dec_deg)
  dd = int(dec_deg)
  am = int((dec_deg - dd) * 60)
  return f"J{hh:02d}{mm:02d}{sign}{dd:02d}{am:02d}"


def _jy(quantity):
  """A flux in Jy, whatever unit the fit record carries it in.

  imfit reports mJy for faint sources; the form wants Jy.
  """
  if isinstance(quantity, (int, float)):
    return _number(quantity)  #bare measurement, already Jy (or Jy/beam)
  if not isinstance(quantity, dict) or quantity.get('value') is None:
    return ''
  value, unit = quantity['value'], (quantity.get('unit') or '').strip()
  if unit.startswith('mJy'):
    value = value / 1000.0
  elif unit.startswith('uJy'):
    value = value / 1e6
  return _number(value)


def _beam_size(beam):
  """Both axes with units and the angle, as the form asks for them."""
  if not beam or beam.get('major_arcsec') is None:
    return ''
  return (f"{_number(beam.get('major_arcsec'), '.4g')}\" x "
          f"{_number(beam.get('minor_arcsec'), '.4g')}\", PA "
          f"{_number(beam.get('position_angle_deg'), '.4g')} deg")


def _calibrator(cal):
  if cal is None:
    return ''
  return _text(getattr(cal, 'listobs_name', '') or getattr(cal, 'name', ''))


def _phase_calibrator(options, phase):
  """The phase calibrator, or 'n/a' when the target served as its own."""
  if getattr(options, 'target_is_phase_cal', None) is True:
    return 'n/a'
  return _calibrator(phase)


def _band(options):
  """Band as the form spells it. listobs says 'U'; the archive wants 'Ku'."""
  band = _text(getattr(options, 'band', ''))
  return 'Ku' if band == 'U' else band


def observation_date(options):
  """Observation date as ISO 'YYYY-MM-DD'.

  listobs scan rows carry 'DD-Mon-YYYY' ('13-Oct-2008'); radio_search dates come
  the other way round, 2-digit, as 'YY-Mon-DD' ('95-Aug-28'), and there the
  century pivot comes from CLI._observation_year rather than being reimplemented
  here. A 4-digit tail is what tells the two apart. Returns '' if unparseable.
  """
  from classes.CLI_input import CLI

  data = getattr(options, 'observation_data', None)
  observations = getattr(data, 'observations', None) or []
  raw = _text(getattr(observations[0], 'date', '')) if observations else ''
  if not raw:
    return ''
  parts = [part.strip() for part in raw.split('-')]
  if len(parts) != 3:
    return ''
  month = _MONTHS.get(parts[1][:3].capitalize())
  if len(parts[2]) == 4 and parts[2].isdigit():
    year, day = int(parts[2]), parts[0]     #listobs: DD-Mon-YYYY
  else:
    year, day = CLI._observation_year(raw), parts[2]   #radio_search: YY-Mon-DD
  if not (year and month and day.isdigit()):
    return ''
  return f"{year:04d}-{month}-{int(day):02d}"


_MONTHS = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
           'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
           'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'}
