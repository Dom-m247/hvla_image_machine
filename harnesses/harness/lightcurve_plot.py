"""A lightcurve sweep's flux densities over time, from each passed run's measurement.

The pipeline measures the target on every run's final image at its catalogue
position (source_fit -> <name>.fit.json): a detection carries a 2D Gaussian fit, a
non-detection an upper limit of detection_sigma times the off-source rms. This
collects those, puts them on a common footing, and plots them per target:

    <sweep>/lightcurve.csv            one row per passed run, plotted or not
    <sweep>/lightcurve_<source>.png   integrated and peak flux density vs time, a row
                                      per band; detections as points, upper limits as
                                      open triangles

Fluxes and limits are measured on the flat-noise image, so they are attenuated by the
primary beam wherever the target sits off the pointing centre -- and a lightcurve sweep
takes pointings up to max_sep_arcsec away. Each is divided by the primary-beam response
at the target, which the pipeline records, so epochs pointed differently compare. An
epoch with no readable response is kept in the CSV but not plotted, rather than mixing
corrected and uncorrected values on one axis.

The threshold can be changed afterwards without re-imaging: `summarize --sigma N`
re-decides every epoch from its recorded S/N. Each run fits a Gaussian whenever its
peak reaches FIT_MIN_SNR, so any threshold down to that has fits to use.

Each epoch is also checked against the archive (the CSV's note column):
  - the pointing offset the data give (the field centre, converted by CASA) against
    the one the archive search reported, which is wrong for an early observation the
    archive lists at untransformed B1950 coordinates;
  - an epoch the data place further than max_sep_arcsec from the target is not
    plotted, whatever the archive said.

Run folders from before target-based measurement (a fit.json with no 'detection') are
still read the old way: the Gaussian at the image peak, which may not be the target.
"""
import csv
import json
import re
from datetime import datetime
from pathlib import Path

import casatasks as ct
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import StrMethodFormatter

from .pipeline import DETECTION_SIGMA, first_value, imstat_dict
from .runner import find_results_dir
from .selection import observation_date, parse_separation_arcsec, read_manifest

CSV_NAME = 'lightcurve.csv'
MJD_EPOCH = datetime(1858, 11, 17)
#For a pointed source the archive's offset and the data's agree to rounding. Beyond
#this they are noted as disagreeing -- a note, not a verdict: catalogue centres of an
#extended object (a cluster) can differ by tens of arcsec as well.
SEPARATION_TOLERANCE_ARCSEC = 10.0

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
SERIES = '#2a78d6'   #one source per plot, so slot 1 throughout; limits differ by shape

COLUMNS = ('source', 'band', 'frequency_ghz', 'time', 'mjd', 'time_from',
           'detected', 'snr', 'threshold_sigma',
           'integrated_flux_jy', 'integrated_flux_err_jy',
           'peak_flux_jy_per_beam', 'peak_flux_err_jy_per_beam', 'upper_limit_jy',
           'rms_jy_per_beam', 'stokes_v_rms_jy_per_beam', 'noise_ratio',
           'pb_response', 'target_separation_arcsec', 'archive_separation',
           'search_epoch', 'fit_offset_arcsec', 'flux_scale', 'config', 'beam_major_arcsec',
           'beam_minor_arcsec', 'converged', 'plotted', 'note',
           'proj_code', 'segment', 'slug', 'fit_json')


def build(sweep, log=print):
  """Write the sweep's lightcurve CSV and one plot per target. Returns the plot paths.

  sweep.options['sigma'], when set, re-decides every epoch at that threshold."""
  rows = collect(sweep, log, sigma=sweep.options.get('sigma'),
                 max_sep=sweep.options.get('max_sep_arcsec'))
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
      shown = [r for r in target_rows if r['plotted']]
      limits = sum(r['detected'] is False for r in shown)
      log(f"Lightcurve plot:  {path}  ({len(shown)} of {len(target_rows)} epoch(s) "
          f"plotted: {len(shown) - limits} detected, {limits} upper limit(s))")
    for r in target_rows:
      if not r['plotted']:
        log(f"  -- {r['slug']}: not plotted ({r['note']})")
      elif r['note']:
        log(f"  .. {r['slug']}: {r['note']}")
  return plots


# ----------------------------------------------------------------- collection
def collect(sweep, log=print, sigma=None, max_sep=None):
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
      rows.append(epoch(selection, fit_path, sigma=sigma, max_sep=max_sep))
    except (OSError, json.JSONDecodeError) as exc:
      log(f"  -- {selection.slug}: could not read {fit_path.name}: {exc}")
  return sorted(rows, key=lambda r: r['time'])


def epoch(selection, fit_path, sigma=None, max_sep=None):
  """A run's measurement, primary-beam corrected, with its observing time."""
  fit = json.loads(fit_path.read_text())
  name = fit_path.name[:-len('.fit.json')]
  results = fit_path.parent
  when, time_from = observed_midpoint(results / f"{name}-listobs.txt"), 'listobs'
  if when is None:
    when, time_from = observation_date(selection), 'archive date'
  known_time = when != datetime.max   #observation_date's 'unreadable'

  beam = fit.get('beam') or {}
  row = {
    'source': selection.name, 'band': selection.band,
    'frequency_ghz': fit.get('frequency_ghz'),
    'time': when, 'mjd': (when - MJD_EPOCH).total_seconds() / 86400 if known_time else None,
    'time_from': time_from,
    'archive_separation': selection.separation,
    'search_epoch': getattr(selection, 'search_epoch', ''),
    'config': selection.config,
    'beam_major_arcsec': beam.get('major_arcsec'),
    'beam_minor_arcsec': beam.get('minor_arcsec'),
    'converged': fit.get('converged'),
    'flux_scale': (fit.get('flux_scale') or {}).get('origin', ''),
    'rms_jy_per_beam': fit.get('rms_jy_per_beam'),
    'stokes_v_rms_jy_per_beam': fit.get('stokes_v_rms_jy_per_beam'),
    'noise_ratio': fit.get('noise_ratio'),
    'proj_code': selection.proj_code, 'segment': selection.segment,
    'slug': selection.slug, 'fit_json': str(fit_path),
    'pb_response': None, 'detected': None, 'plotted': False, 'note': '',
    #every column present on every row; set below only where measured
    'snr': None, 'threshold_sigma': None, 'upper_limit_jy': None,
    'integrated_flux_jy': None, 'integrated_flux_err_jy': None,
    'peak_flux_jy_per_beam': None, 'peak_flux_err_jy_per_beam': None,
    'target_separation_arcsec': None, 'fit_offset_arcsec': None,
  }
  if not known_time:
    row['note'] = 'no observing time (listobs missing, archive date unreadable)'
    return row
  if 'detection' not in fit:
    return _peak_fit_epoch(row, fit, results, name)
  return _target_epoch(row, fit, selection, sigma, max_sep)


def _target_epoch(row, fit, selection, sigma, max_sep):
  """An epoch measured at the target's catalogue position: a detection with its
  Gaussian fit (or, failing a usable fit, its peak pixel), or an upper limit."""
  target, detection = fit.get('target') or {}, fit.get('detection') or {}
  notes = []
  scale = fit.get('flux_scale') or {}
  if scale.get('origin') == 'catalogue':
    notes.append(f"FLUX SCALE FROM CATALOGUE ({scale.get('calibrator')} at "
                 f"{scale.get('flux_jy')} Jy, quality {scale.get('quality') or '?'}; "
                 f"no standard flux calibrator observed)")
  data_sep = target.get('separation_from_pointing_arcsec')
  archive_sep = parse_separation_arcsec(selection.separation)
  row['target_separation_arcsec'] = data_sep
  if (data_sep is not None and archive_sep is not None
      and abs(data_sep - archive_sep) > SEPARATION_TOLERANCE_ARCSEC):
    notes.append(f'pointed {data_sep:.0f}" from the target by the data, {archive_sep:.0f}" '
                 f'by the archive ({row["search_epoch"] or "J2000"} search)')
  if max_sep is not None and data_sep is not None and data_sep > max_sep + SEPARATION_TOLERANCE_ARCSEC:
    row['note'] = '; '.join(notes + [f'beyond max_sep ({max_sep:g}")'])
    return row
  if not target.get('in_image'):
    row['note'] = '; '.join(notes + ['target outside the image'])
    return row
  response = target.get('pb_response')
  if not response or not 0 < response <= 1.001:
    row['note'] = '; '.join(notes + ['no primary-beam response at the target'])
    return row
  row['pb_response'] = response

  snr = detection.get('snr')
  rms = detection.get('rms_jy_per_beam') or fit.get('rms_jy_per_beam')
  threshold = sigma or detection.get('threshold_sigma') or DETECTION_SIGMA
  row['snr'], row['threshold_sigma'] = snr, threshold
  if snr is None or not rms:
    row['note'] = '; '.join(notes + ['the image could not be measured at the target'])
    return row
  row['fit_offset_arcsec'] = fit.get('offset_from_target_arcsec')
  row['detected'] = snr >= threshold
  if not row['detected']:
    row['upper_limit_jy'] = threshold * rms / response
  else:
    integrated, peak = fit.get('integrated_flux') or {}, fit.get('peak_flux') or {}
    offset, radius = fit.get('offset_from_target_arcsec'), detection.get('search_radius_arcsec')
    wandered = offset is not None and radius is not None and offset > radius
    if fit.get('converged') and integrated.get('value') is not None and not wandered:
      #errors scale with the flux: the correction is a constant factor at this position
      row['integrated_flux_jy'] = _scaled(integrated.get('value'), response)
      row['integrated_flux_err_jy'] = _scaled(integrated.get('error'), response)
      row['peak_flux_jy_per_beam'] = _scaled(peak.get('value'), response)
      row['peak_flux_err_jy_per_beam'] = _scaled(peak.get('error'), response)
    else:
      #detected, but no Gaussian to trust: the brightest pixel at the target stands in
      #for the peak, with the rms as its error, and there is no integrated flux
      row['peak_flux_jy_per_beam'] = _scaled(detection.get('peak_jy_per_beam'), response)
      row['peak_flux_err_jy_per_beam'] = _scaled(rms, response)
      why = ('no fit was made' if fit.get('converged') is None
             else 'the fit did not converge' if not fit.get('converged')
             else f'the fit landed {offset:.1f}" from the target')
      notes.append(f'peak pixel only ({why})')
  row['plotted'] = True
  row['note'] = '; '.join(notes)
  return row


def _peak_fit_epoch(row, fit, results, name):
  """An epoch from before target-based measurement: the Gaussian the pipeline fitted
  at the image peak, which may not be the target. Kept so older sweeps summarize."""
  integrated, peak = fit.get('integrated_flux') or {}, fit.get('peak_flux') or {}
  if not fit.get('converged'):
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
  row['integrated_flux_jy'] = _scaled(integrated.get('value'), response)
  row['integrated_flux_err_jy'] = _scaled(integrated.get('error'), response)
  row['peak_flux_jy_per_beam'] = _scaled(peak.get('value'), response)
  row['peak_flux_err_jy_per_beam'] = _scaled(peak.get('error'), response)
  row['plotted'] = True
  row['note'] = 'measured at the image peak, not the target (run predates target-based measurement)'
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
  """Primary-beam response at the fitted source's peak pixel, or None. Only for run
  folders from before the pipeline recorded the response at the target itself.

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

#detections and limits are one source, so they share its color and differ by shape:
#a filled circle, and the open downward triangle radio lightcurves use for a limit
DETECTION_STYLE = dict(marker='o', markersize=7, color=SERIES, markeredgecolor=SURFACE,
                       markeredgewidth=1.5)
LIMIT_STYLE = dict(marker='v', markersize=8, markerfacecolor=SURFACE,
                   markeredgecolor=SERIES, markeredgewidth=1.5)
#an epoch whose flux scale came from a calibrator's catalogue flux (no standard flux
#calibrator observed) keeps its kind of mark but in outline: an open circle, and the
#line-drawn downward tri for a limit
CATALOGUE_DETECTION_STYLE = dict(marker='o', markersize=7, markerfacecolor=SURFACE,
                                 markeredgecolor=SERIES, markeredgewidth=1.5)
CATALOGUE_LIMIT_STYLE = dict(marker='1', markersize=11, color=SERIES, markeredgewidth=1.8)


def plot(source, rows, path, subtitle=''):
  """Integrated and peak flux density vs time, one row of panels per band.

  Bands sit in separate rows rather than sharing an axis: a spectral index puts
  them at different levels, and the two measures have different units. An upper
  limit is drawn in both panels -- for an unresolved source, Jy/beam is Jy.
  """
  shown = [r for r in rows if r['plotted']]
  if not shown:
    return False
  bands = sorted(dict.fromkeys(r['band'] for r in shown),
                 key=lambda b: _median([r['frequency_ghz'] or 0 for r in shown if r['band'] == b]))
  thresholds = sorted({r['threshold_sigma'] for r in shown if r.get('threshold_sigma')})
  any_limit = any(r['detected'] is False for r in shown)

  fig = Figure(figsize=(11, 1.6 + 2.8 * len(bands)), facecolor=SURFACE, layout='constrained')
  axes = fig.subplots(len(bands), len(PANELS), sharex=True, squeeze=False)
  for row_axes, band in zip(axes, bands):
    band_rows = [r for r in shown if r['band'] == band]
    ghz = _median([r['frequency_ghz'] for r in band_rows if r['frequency_ghz']])
    label = f"{band} band" + (f" ({ghz:.2f} GHz)" if ghz else '')
    limits = [r for r in band_rows if r['detected'] is False and r.get('upper_limit_jy')]
    for ax, (value_key, error_key, measure, unit) in zip(row_axes, PANELS):
      _style(ax)
      points = [r for r in band_rows if r.get(value_key) is not None]
      if points:
        ax.errorbar([r['time'] for r in points],
                    [r[value_key] * 1e3 for r in points],
                    yerr=[(r.get(error_key) or 0) * 1e3 for r in points],
                    fmt='none', ecolor=SERIES, elinewidth=1.5, capsize=0, zorder=2)
      for marks, value, standard, catalogue in ((points, value_key, DETECTION_STYLE,
                                                 CATALOGUE_DETECTION_STYLE),
                                                (limits, 'upper_limit_jy', LIMIT_STYLE,
                                                 CATALOGUE_LIMIT_STYLE)):
        for style, chosen in ((standard, [r for r in marks if not _catalogue(r)]),
                              (catalogue, [r for r in marks if _catalogue(r)])):
          if chosen:
            ax.plot([r['time'] for r in chosen], [r[value] * 1e3 for r in chosen],
                    linestyle='none', zorder=3, **style)
      ax.set_title(f"{label} — {measure.lower()}", loc='left', fontsize=10,
                   color=INK_SECONDARY)
      ax.set_ylabel(unit, color=INK_MUTED, fontsize=9)
      #plain, comma'd numbers: an offset ('+3.8e1') on a flux axis reads as a different value
      ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,g}'))

  locator = AutoDateLocator(minticks=3, maxticks=8)
  for ax in axes[-1]:
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))

  #the legend names only the marks actually drawn
  limit_name = (f"{thresholds[0]:g}σ upper limit" if len(thresholds) == 1 else "upper limit")
  handles = []
  kinds = ((lambda r: r['detected'] is not False, 'detection', DETECTION_STYLE,
            CATALOGUE_DETECTION_STYLE),
           (lambda r: r['detected'] is False, limit_name, LIMIT_STYLE, CATALOGUE_LIMIT_STYLE))
  for wanted, name, standard, catalogue in kinds:
    if any(wanted(r) and not _catalogue(r) for r in shown):
      handles.append(Line2D([], [], linestyle='none', label=name, **standard))
    if any(wanted(r) and _catalogue(r) for r in shown):
      handles.append(Line2D([], [], linestyle='none', label=f"{name}, catalogue flux scale",
                            **catalogue))
  fig.legend(handles=handles, loc='outside upper right', ncols=len(handles), frameon=False,
             fontsize=9, labelcolor=INK_SECONDARY)
  fig.suptitle(f"{source} lightcurve", x=0.01, ha='left', fontsize=13, color=INK)
  dropped = len(rows) - len(shown)
  #two lines: on one, the caveats run off the right edge of a one-band figure
  fig.supxlabel(f"{subtitle}   ·   {len(shown)} epoch(s)"
                + (f", {dropped} not plotted (see {CSV_NAME})" if dropped else '')
                + "\nprimary-beam corrected   ·   error bars are imfit's (no flux-scale term)"
                + ("   ·   limits are the threshold times the off-source rms" if any_limit else '')
                + ("\noutlined marks: no standard flux calibrator observed; scale from the "
                   "calibrator's catalogue flux, uncertain by 10-20% or more"
                   if any(_catalogue(r) for r in shown) else ''),
                x=0.01, ha='left', fontsize=8, color=INK_MUTED, linespacing=1.6)
  fig.savefig(path, dpi=110, facecolor=SURFACE)
  return True


def _catalogue(row):
  return row.get('flux_scale') == 'catalogue'


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
