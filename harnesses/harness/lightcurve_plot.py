"""A lightcurve sweep's flux densities over time, from each passed run's source fit.

The pipeline already fits a 2D Gaussian to every run's final image
(source_fit -> <name>.fit.json). This collects those fits, puts them on a common
footing, and plots them per target:

    <sweep>/lightcurve.csv            one row per passed run, plotted or not
    <sweep>/lightcurve_<source>.png   integrated and peak flux density vs time, a row per band

The fit is made on the flat-noise image, so its fluxes are attenuated by the primary
beam wherever the target sits off the pointing centre -- and a lightcurve sweep takes
pointings up to max_sep_arcsec away. Each fit is divided by the primary-beam response
at the fitted peak, read back from the results folder (<name>.fits over
<name>.pbcor.tt0), so epochs pointed differently compare. An epoch with no readable
response is kept in the CSV but not plotted, rather than mixing corrected and
uncorrected fluxes on one axis.
"""
import csv
import json
import re
from datetime import datetime
from pathlib import Path

import casatasks as ct
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.figure import Figure
from matplotlib.ticker import StrMethodFormatter

from .pipeline import first_value, imstat_dict
from .runner import find_results_dir
from .selection import observation_date, read_manifest

CSV_NAME = 'lightcurve.csv'
MJD_EPOCH = datetime(1858, 11, 17)

#'Observed from   03-Aug-1991/00:00:20.0   to   03-Aug-1991/00:02:30.0 (TAI)'.
#parse_listobs.parse_obs_info reads the same line, but importing it runs the
#data_calibration package, which loads casaplotms.
OBSERVED = re.compile(r'Observed from\s+(\S+)\s+to\s+(\S+)')
LISTOBS_TIME = '%d-%b-%Y/%H:%M:%S.%f'

#the reference palette's light surface and chrome (dataviz skill, palette.md)
SURFACE = '#fcfcfb'
INK = '#0b0b0b'
INK_SECONDARY = '#52514e'
INK_MUTED = '#898781'
GRID = '#e1e0d9'
AXIS = '#c3c2b7'
SERIES = '#2a78d6'   #one series per panel, so slot 1 throughout

COLUMNS = ('source', 'band', 'frequency_ghz', 'time', 'mjd', 'time_from',
           'integrated_flux_jy', 'integrated_flux_err_jy',
           'peak_flux_jy_per_beam', 'peak_flux_err_jy_per_beam',
           'pb_response', 'separation', 'config', 'beam_major_arcsec',
           'beam_minor_arcsec', 'converged', 'plotted', 'note',
           'proj_code', 'segment', 'slug', 'fit_json')


def build(sweep, log=print):
  """Write the sweep's lightcurve CSV and one plot per target. Returns the plot paths."""
  rows = collect(sweep, log)
  if not rows:
    log('Lightcurve: no passed run has a source fit yet; nothing to plot.')
    return []
  write_csv(rows, sweep.root / CSV_NAME)
  log(f"\nLightcurve table: {sweep.root / CSV_NAME}")
  plots = []
  for source in dict.fromkeys(r['source'] for r in rows):
    target_rows = [r for r in rows if r['source'] == source]
    path = sweep.root / f"lightcurve_{_safe(source)}.png"
    if plot(source, target_rows, path, subtitle=sweep.root.name):
      plots.append(path)
      shown = sum(r['plotted'] for r in target_rows)
      log(f"Lightcurve plot:  {path}  ({shown} of {len(target_rows)} epoch(s) plotted)")
    for r in target_rows:
      if not r['plotted']:
        log(f"  -- {r['slug']}: not plotted ({r['note']})")
  return plots


# ----------------------------------------------------------------- collection
def collect(sweep, log=print):
  """One row per passed run that has a fit record, oldest first."""
  try:
    report = json.loads(sweep.report_path.read_text())
  except (OSError, json.JSONDecodeError):
    return []
  passed = {r['slug'] for r in report.get('runs', []) if r.get('status') == 'passed'}
  rows = []
  for selection in read_manifest(sweep.manifest):
    if selection.slug not in passed:
      continue
    results = find_results_dir(sweep.runs_dir / selection.slug)
    fit_path = next(iter(sorted(results.glob('*.fit.json'))), None) if results else None
    if fit_path is None:
      log(f"  -- {selection.slug}: passed, but its results folder has no fit record")
      continue
    try:
      rows.append(epoch(selection, fit_path))
    except (OSError, json.JSONDecodeError) as exc:
      log(f"  -- {selection.slug}: could not read {fit_path.name}: {exc}")
  return sorted(rows, key=lambda r: r['time'])


def epoch(selection, fit_path):
  """A run's fit, primary-beam corrected, with its observing time."""
  fit = json.loads(fit_path.read_text())
  name = fit_path.name[:-len('.fit.json')]
  results = fit_path.parent
  when, time_from = observed_midpoint(results / f"{name}-listobs.txt"), 'listobs'
  if when is None:
    when, time_from = observation_date(selection), 'archive date'
  known_time = when != datetime.max   #observation_date's 'unreadable'

  integrated, peak = fit.get('integrated_flux') or {}, fit.get('peak_flux') or {}
  beam = fit.get('beam') or {}
  row = {
    'source': selection.name, 'band': selection.band,
    'frequency_ghz': fit.get('frequency_ghz'),
    'time': when, 'mjd': (when - MJD_EPOCH).total_seconds() / 86400 if known_time else None,
    'time_from': time_from,
    'separation': selection.separation, 'config': selection.config,
    'beam_major_arcsec': beam.get('major_arcsec'),
    'beam_minor_arcsec': beam.get('minor_arcsec'),
    'converged': bool(fit.get('converged')),
    'proj_code': selection.proj_code, 'segment': selection.segment,
    'slug': selection.slug, 'fit_json': str(fit_path),
    'pb_response': None, 'plotted': False, 'note': '',
  }
  if not known_time:
    row['note'] = 'no observing time (listobs missing, archive date unreadable)'
    return row
  if not row['converged']:
    row['note'] = 'fit did not converge'
    return row
  if integrated.get('value') is None:
    row['note'] = 'fit has no flux'
    return row
  response = pb_response(results / f"{name}.fits", results / f"{name}.pbcor.tt0",
                         fit.get('fit_box', ''))
  if not response:
    row['note'] = 'no primary-beam response (pbcor image missing or unreadable)'
    return row
  row['pb_response'] = response
  #errors scale with the flux: the correction is a constant factor at this position
  row['integrated_flux_jy'] = _scaled(integrated.get('value'), response)
  row['integrated_flux_err_jy'] = _scaled(integrated.get('error'), response)
  row['peak_flux_jy_per_beam'] = _scaled(peak.get('value'), response)
  row['peak_flux_err_jy_per_beam'] = _scaled(peak.get('error'), response)
  row['plotted'] = True
  return row


def observed_midpoint(listobs):
  """Middle of the target's observing span, from the results folder's listobs."""
  try:
    match = OBSERVED.search(Path(listobs).read_text(errors='replace'))
  except OSError:
    return None
  if not match:
    return None
  try:
    start, end = (datetime.strptime(t, LISTOBS_TIME) for t in match.groups())
  except ValueError:
    return None
  return start + (end - start) / 2


def pb_response(flat, pbcor, box=''):
  """Primary-beam response at the fitted source's peak pixel, or None.

  impbcor divides the flat image by the pb pixel by pixel, so flat/pbcor at any
  non-blank pixel is exactly the pb there. The peak pixel stands in for the fitted
  centroid: the fit box is a few beams across, the primary beam arcminutes.
  """
  if not (Path(flat).exists() and Path(pbcor).is_dir()):
    return None
  try:
    kwargs = {'imagename': str(flat)}
    if box and not box.startswith('('):   #'(whole image)' means no box
      kwargs['box'] = box
    maxpos = imstat_dict(**kwargs).get('maxpos')
    if maxpos is None:
      return None
    x, y = int(maxpos[0]), int(maxpos[1])
    at = f"{x},{y},{x},{y}"
    flat_value = first_value((ct.imval(imagename=str(flat), box=at) or {}).get('data'))
    pbcor_value = first_value((ct.imval(imagename=str(pbcor), box=at) or {}).get('data'))
  except Exception as exc:
    print(f"  pb_response: could not read {flat} / {pbcor}: {exc}")
    return None
  if not flat_value or not pbcor_value:
    return None
  response = flat_value / pbcor_value
  return response if 0 < response <= 1.001 else None


def _scaled(value, response):
  return value / response if value is not None else None


def write_csv(rows, path):
  with open(path, 'w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
      known = row['mjd'] is not None
      writer.writerow({**row, 'time': row['time'].isoformat(timespec='seconds') if known else '',
                       'mjd': f"{row['mjd']:.5f}" if known else ''})


# ------------------------------------------------------------------- plotting
PANELS = (('integrated_flux_jy', 'integrated_flux_err_jy', 'Integrated flux density', 'mJy'),
          ('peak_flux_jy_per_beam', 'peak_flux_err_jy_per_beam', 'Peak flux density', 'mJy/beam'))


def plot(source, rows, path, subtitle=''):
  """Integrated and peak flux density vs time, one row of panels per band.

  Bands sit in separate rows rather than sharing an axis: a spectral index puts
  them at different levels, and the two measures have different units.
  """
  shown = [r for r in rows if r['plotted']]
  if not shown:
    return False
  bands = sorted(dict.fromkeys(r['band'] for r in shown),
                 key=lambda b: _median([r['frequency_ghz'] or 0 for r in shown if r['band'] == b]))

  fig = Figure(figsize=(11, 1.4 + 2.8 * len(bands)), facecolor=SURFACE, layout='constrained')
  axes = fig.subplots(len(bands), len(PANELS), sharex=True, squeeze=False)
  for row_axes, band in zip(axes, bands):
    band_rows = [r for r in shown if r['band'] == band]
    ghz = _median([r['frequency_ghz'] for r in band_rows if r['frequency_ghz']])
    label = f"{band} band" + (f" ({ghz:.2f} GHz)" if ghz else '')
    for ax, (value_key, error_key, measure, unit) in zip(row_axes, PANELS):
      _style(ax)
      points = [r for r in band_rows if r[value_key] is not None]
      ax.errorbar([r['time'] for r in points],
                  [r[value_key] * 1e3 for r in points],
                  yerr=[(r[error_key] or 0) * 1e3 for r in points],
                  fmt='o', color=SERIES, markersize=7, markeredgecolor=SURFACE,
                  markeredgewidth=1.5, elinewidth=1.5, capsize=0, zorder=3)
      ax.set_title(f"{label} — {measure.lower()}", loc='left', fontsize=10,
                   color=INK_SECONDARY)
      ax.set_ylabel(unit, color=INK_MUTED, fontsize=9)
      #plain, comma'd numbers: an offset ('+3.8e1') on a flux axis reads as a different value
      ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,g}'))

  locator = AutoDateLocator(minticks=3, maxticks=8)
  for ax in axes[-1]:
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))

  fig.suptitle(f"{source} lightcurve", x=0.01, ha='left', fontsize=13, color=INK)
  dropped = len(rows) - len(shown)
  fig.supxlabel(f"{subtitle}   ·   {len(shown)} epoch(s)"
                + (f", {dropped} not plotted (see {CSV_NAME})" if dropped else '')
                + "   ·   primary-beam corrected; error bars are imfit's "
                  "(no flux-scale term)",
                x=0.01, ha='left', fontsize=8, color=INK_MUTED)
  fig.savefig(path, dpi=110, facecolor=SURFACE)
  return True


def _style(ax):
  ax.set_facecolor(SURFACE)
  for side in ('top', 'right', 'left'):
    ax.spines[side].set_visible(False)
  ax.spines['bottom'].set_color(AXIS)
  ax.spines['bottom'].set_linewidth(0.8)
  ax.tick_params(colors=INK_MUTED, labelsize=8, length=0, pad=4)
  ax.grid(axis='y', color=GRID, linewidth=0.7, linestyle='-')
  ax.set_axisbelow(True)


def _median(values):
  values = sorted(v for v in values if v is not None)
  return values[len(values) // 2] if values else None


def _safe(name):
  return re.sub(r'[^A-Za-z0-9.+-]+', '_', name).strip('_') or 'source'
