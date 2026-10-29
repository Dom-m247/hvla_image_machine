"""A lightcurve sweep's flux densities over time, from each passed run's source fit.

The pipeline already fits a 2D Gaussian to every run's final image
(source_fit -> <name>.fit.json). This collects those fits, puts them on a common
footing, and plots them per target:

    <sweep>/lightcurve.csv            one row per passed run, plotted or not
    <sweep>/lightcurve_<source>.png   integrated and peak flux density vs time, a row per band
    <sweep>/lightcurve_<source>.csv   the points that plot shows, in its units (mJy)
    <sweep>/lightcurve_<source>_config_<cfg>.{png,csv}   the same, one array config's epochs
    <sweep>/lightcurve_<source>[_config_<cfg>]_{integrated,peak}.png   its two columns, a png each

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
import math
import re
from datetime import datetime, timedelta
from pathlib import Path

import casatasks as ct
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter, date2num
from matplotlib.figure import Figure
from matplotlib.path import Path as LinePath
from matplotlib.transforms import Bbox
from matplotlib.ticker import StrMethodFormatter

from .pipeline import CLI, first_value, imstat_dict
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
#lightcurve.csv's Jy columns -> the plot CSV's mJy ones
MJY_COLUMNS = {'integrated_flux_jy': 'integrated_flux_mjy',
               'integrated_flux_err_jy': 'integrated_flux_err_mjy',
               'peak_flux_jy_per_beam': 'peak_flux_mjy_per_beam',
               'peak_flux_err_jy_per_beam': 'peak_flux_err_mjy_per_beam'}
PLOT_COLUMNS = ('band', 'frequency_ghz', 'time', 'mjd', 'proj_code', 'config',
                *MJY_COLUMNS.values(), 'slug')


def build(sweep, log=print, label_points=True, ask_exclude=False, by_config=False,
          separate_flux=False):
  """Write the sweep's lightcurve CSV, and per target a plot and a CSV of the points
  it shows. Returns the plot paths. label_points puts each epoch's project code
  beside its point; ask_exclude asks which project codes to leave off the plots;
  by_config draws each array configuration's epochs as images of their own
  (_config_<cfg>); separate_flux draws integrated and peak flux as a png each."""
  rows = collect(sweep, log)
  if not rows:
    log('Lightcurve: no passed run has a source fit yet; nothing to plot.')
    return []
  if ask_exclude:
    plotted = sorted({r['proj_code'] for r in rows if r['plotted']})
    excluded = set(CLI.getExcludedProjects(plotted)) if plotted else set()
    for r in rows:
      if r['plotted'] and r['proj_code'] in excluded:
        r['plotted'], r['note'] = False, 'excluded on replot'
  write_csv(rows, sweep.root / CSV_NAME)
  log(f"\nLightcurve table: {sweep.root / CSV_NAME}")
  plots = []
  for source in dict.fromkeys(r['source'] for r in rows):
    target_rows = [r for r in rows if r['source'] == source]
    stem = f"lightcurve_{_safe(source)}"
    if by_config:
      span = time_span(target_rows)   #so a target's config images line up
      sets = [(f"{stem}_config_{_safe(c) if c else 'unknown'}",
               [r for r in target_rows if r['config'] == c],
               f"{c} config" if c else 'config unknown')
              for c in config_order(target_rows)]
    else:
      span, sets = None, [(stem, target_rows, '')]
    for set_stem, set_rows, heading in sets:
      plots += draw(source, set_rows, sweep.root, set_stem, log, heading=heading, span=span,
                    label_points=label_points, separate_flux=separate_flux)
    for r in target_rows:
      if not r['plotted']:
        log(f"  -- {r['slug']}: not plotted ({r['note']})")
  return plots


def draw(source, rows, root, stem, log=print, heading='', span=None, label_points=True,
         separate_flux=False):
  """<stem>.png (or _integrated.png and _peak.png) and <stem>.csv of their points.
  Returns the pngs drawn; none when no row is plotted."""
  figures = ([(f"{stem}_{name}.png", (panel,)) for name, panel in zip(PANEL_FILES, PANELS)]
             if separate_flux else [(f"{stem}.png", PANELS)])
  drawn = []
  for name, panels in figures:
    if plot(source, rows, root / name, subtitle=root.name, label_points=label_points,
            panels=panels, heading=heading, span=span):
      drawn.append(root / name)
  if drawn:
    write_plot_csv(rows, root / f"{stem}.csv")
    shown = sum(r['plotted'] for r in rows)
    for path in drawn:
      log(f"Lightcurve plot:  {path}  ({shown} of {len(rows)} epoch(s) plotted)")
    log(f"Plotted points:   {root / f'{stem}.csv'}")
  return drawn


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


def write_plot_csv(rows, path):
  """The points a target's plot shows, band by band in its order, in mJy."""
  shown = [r for r in rows if r['plotted']]
  with open(path, 'w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=PLOT_COLUMNS, extrasaction='ignore')
    writer.writeheader()
    for band in band_order(shown):
      for row in (r for r in shown if r['band'] == band):
        writer.writerow({**row, 'time': row['time'].isoformat(timespec='seconds'),
                         'mjd': f"{row['mjd']:.5f}",
                         **{mjy: row[jy] * 1e3 if row[jy] is not None else ''
                            for jy, mjy in MJY_COLUMNS.items()}})


# ------------------------------------------------------------------- plotting
PANELS = (('integrated_flux_jy', 'integrated_flux_err_jy', 'Integrated flux density', 'mJy'),
          ('peak_flux_jy_per_beam', 'peak_flux_err_jy_per_beam', 'Peak flux density', 'mJy/beam'))
PANEL_FILES = ('integrated', 'peak')   #each panel's png suffix when they're drawn apart
CONFIG_ORDER = ('A', 'AB', 'B', 'BC', 'C', 'CD', 'D')   #longest baselines first; hybrids between


def band_order(rows):
  """The rows' bands, lowest frequency first: the order plot() stacks them in."""
  return sorted(dict.fromkeys(r['band'] for r in rows),
                key=lambda b: _median([r['frequency_ghz'] or 0 for r in rows if r['band'] == b]) or 0)


def config_order(rows):
  """The rows' array configs in CONFIG_ORDER, any it doesn't know after, unknown last."""
  return sorted(dict.fromkeys(r['config'] for r in rows),
                key=lambda c: (not c, CONFIG_ORDER.index(c) if c in CONFIG_ORDER
                               else len(CONFIG_ORDER), c))


def time_span(rows):
  """The plotted rows' first and last times, padded by matplotlib's default 5% margin."""
  times = [r['time'] for r in rows if r['plotted']]
  if not times:
    return None
  pad = max((max(times) - min(times)) * 0.05, timedelta(days=30))
  return min(times) - pad, max(times) + pad


def plot(source, rows, path, subtitle='', label_points=True, panels=PANELS, heading='',
         span=None):
  """Flux density vs time, a column per entry of panels (integrated and peak by
  default) and a row per band.

  Bands sit in separate rows rather than sharing an axis: a spectral index puts
  them at different levels. A row's panels share one flux scale. label_points
  writes each epoch's project code beside its point; heading follows the title;
  span fixes the time axis' (start, end).
  """
  shown = [r for r in rows if r['plotted']]
  if not shown:
    return False
  bands = band_order(shown)

  fig = Figure(figsize=(11, 1.4 + 2.8 * len(bands)), facecolor=SURFACE, layout='constrained')
  axes = fig.subplots(len(bands), len(panels), sharex=True, sharey='row', squeeze=False)
  if span:
    axes[0][0].set_xlim(*span)
  labelled = []
  for row_axes, band in zip(axes, bands):
    band_rows = [r for r in shown if r['band'] == band]
    ghz = _median([r['frequency_ghz'] for r in band_rows if r['frequency_ghz']])
    label = f"{band} band" + (f" ({ghz:.2f} GHz)" if ghz else '')
    for ax, (value_key, error_key, measure, unit) in zip(row_axes, panels):
      _style(ax)
      points = [r for r in band_rows if r[value_key] is not None]
      ax.errorbar([r['time'] for r in points],
                  [r[value_key] * 1e3 for r in points],
                  yerr=[(r[error_key] or 0) * 1e3 for r in points],
                  fmt='o-', color=SERIES, linewidth=1.2, markersize=7,
                  markeredgecolor=SURFACE, markeredgewidth=1.5, elinewidth=1.5,
                  capsize=0, zorder=3)
      ax.set_title(f"{label} — {measure.lower()}", loc='left', fontsize=10,
                   color=INK_SECONDARY)
      ax.set_ylabel(f"{measure} ({unit})", color=INK_MUTED, fontsize=9)
      #sharey hides the peak panel's tick labels; its unit differs, so it keeps them
      ax.yaxis.set_tick_params(labelleft=True)
      #plain, comma'd numbers: an offset ('+3.8e1') on a flux axis reads as a different value
      ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,g}'))
      if label_points:
        labelled.append((ax, points, value_key))

  locator = AutoDateLocator(minticks=3, maxticks=8)
  for ax in axes[-1]:
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))
    ax.set_xlabel('Observation date', color=INK_MUTED, fontsize=9)

  fig.suptitle(f"{source} lightcurve" + (f" — {heading}" if heading else ''),
               x=0.01, ha='left', fontsize=13, color=INK)
  dropped = len(rows) - len(shown)
  fig.supxlabel(f"{subtitle}   ·   {len(shown)} epoch(s)"
                + (f", {dropped} not plotted (see {CSV_NAME})" if dropped else '')
                + "   ·   primary-beam corrected; error bars are imfit's "
                  "(no flux-scale term)",
                x=0.01, ha='left', fontsize=8, color=INK_MUTED)
  if labelled:
    _label_points(fig, labelled)
  fig.savefig(path, dpi=110, facecolor=SURFACE)
  return True


#where a project label may sit, tried in order: right, left, above, below the point
LABEL_SPOTS = (((7, 0), 'left', 'center'), ((-7, 0), 'right', 'center'),
               ((0, 7), 'center', 'bottom'), ((0, -7), 'center', 'top'))
LABEL_SHARE_PT = 30   #a same-project point this close to a labelled one shares its label


def _label_points(fig, labelled):
  """Project code beside each point, in the first LABEL_SPOTS spot that stays inside
  the panel and clear of the other labels, points and the line joining them; where
  none is clear, the first spot. Needs the final layout, so it runs last, on a drawn figure."""
  canvas = FigureCanvasAgg(fig)
  canvas.draw()
  renderer = canvas.get_renderer()
  px_per_pt = fig.dpi / 72
  share = LABEL_SHARE_PT * px_per_pt
  pad = 4 * px_per_pt   #about a marker's radius
  for ax, points, value_key in labelled:
    frame = ax.get_window_extent(renderer)
    xy = [(r['time'], r[value_key] * 1e3) for r in points]
    at = ax.transData.transform([(date2num(t), v) for t, v in xy])
    markers = [Bbox.from_extents(x - pad, y - pad, x + pad, y + pad) for x, y in at]
    line = LinePath(at) if len(at) > 1 else None
    placed = []   #(project, display position, label box)
    for r, point, here in zip(points, xy, at):
      code = r['proj_code']
      if any(c == code and math.dist(p, here) < share for c, p, _ in placed):
        continue
      for spot in LABEL_SPOTS:
        label = _annotate(ax, code, point, *spot)
        box = label.get_window_extent(renderer)
        inside = (frame.x0 <= box.x0 and box.x1 <= frame.x1
                  and frame.y0 <= box.y0 and box.y1 <= frame.y1)
        if (inside and not any(box.overlaps(b) for b in markers + [b for *_, b in placed])
            and not (line and line.intersects_bbox(box, filled=False))):
          break
        label.remove()
      else:
        box = _annotate(ax, code, point, *LABEL_SPOTS[0]).get_window_extent(renderer)
      placed.append((code, here, box))


def _annotate(ax, text, point, offset, ha, va):
  label = ax.annotate(text, point, xytext=offset, textcoords='offset points',
                      ha=ha, va=va, fontsize=7, color=INK_SECONDARY, zorder=4)
  label.set_in_layout(False)   #keep the layout the placement was measured on
  return label


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
