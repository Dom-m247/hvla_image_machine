"""Outlier fields: a bright source outside the main image gets its own tclean field so its
sidelobes are cleaned out of the main image, and a target outside it gets a field to be
measured in. Sources come from a shallow, tapered clean of the primary beam (no catalogue)."""
import math
from pathlib import Path

import casatasks as ct
import casatools
import numpy as np
from scipy import ndimage

from classes import image_data, run_log
from classes.constants import (
  CLEAN_PBLIMIT, OUTLIER_FIELD_MAX_PX, OUTLIER_FIELD_MIN_PX, OUTLIER_FIELD_SUFFIX,
  OUTLIER_MARGIN_BEAMS, OUTLIER_MAX_FIELDS, OUTLIER_MERGE_BEAMS, OUTLIER_MIN_APPARENT_JY,
  OUTLIER_SWEEP_DYNAMIC_RANGE, OUTLIER_SWEEP_IMSIZE, OUTLIER_SWEEP_NITER, OUTLIER_SWEEP_NSIGMA,
  OUTLIER_SWEEP_RADIUS_FWHM, OUTLIER_SWEEP_SUFFIX, OUTLIER_TARGET_FIELD_PX, PB_EDGE_FWHM,
  PB_FWHM_ARCMIN_GHZ, TARGET_FIELD_SUFFIX)

TARGET_LABEL = TARGET_FIELD_SUFFIX.lstrip('_')
#tclean won't clean where its beam is under this, and fails outright on a field with no
#pixel above it, so every field must hold its source above it on the search image
PB_LIMIT = abs(CLEAN_PBLIMIT)


def plan(options, cell_arcsec, beam_arcsec=None):
  '''Choose the run's outlier fields, store them on options.outlier_fields and return them.
  beam_arcsec is the expected synthesized beam. A failed search images without fields.'''
  try:
    fields = _plan(options, cell_arcsec, beam_arcsec)
  except Exception as exc:
    _say(f"outlier-field search failed ({exc}); imaging without outlier fields")
    fields = []
  options.outlier_fields = fields
  return fields


def tclean_kwargs(options, imagename):
  '''{'outlierfile': <imagename>.outliers.txt} naming this clean's fields; {} when the
  run has none. Each field gets a whole-field box mask, or reuses the one it has.'''
  fields = getattr(options, 'outlier_fields', None)
  if not fields:
    return {}
  lines = []
  for field in fields:
    n = field['imsize']
    name = f"{imagename}{field['suffix']}"
    #a restart refuses mask= beside an existing .mask; an empty value reuses it
    box = '' if Path(name + '.mask').exists() else f"box[[0pix,0pix],[{n - 1}pix,{n - 1}pix]]"
    lines += [f"imagename={name}",
              f"imsize=[{n},{n}]",
              f"phasecenter={field['frame']} {field['ra_rad']:.12f}rad {field['dec_rad']:.12f}rad",
              'usemask=user',
              f"mask={box}"]
  path = f"{imagename}.outliers.txt"
  Path(path).write_text('\n'.join(lines) + '\n')
  return {'outlierfile': path}


def product_globs(base):
  '''Glob patterns for the field images a clean of `base` writes beside its own.'''
  return [base + OUTLIER_FIELD_SUFFIX + '[0-9][0-9].*', base + TARGET_FIELD_SUFFIX + '.*']


def export(options, base, results_dir, name):
  '''FITS of each field of the image `base` into the results folder; the target's field
  also gets a primary-beam-corrected copy.'''
  for field in getattr(options, 'outlier_fields', None) or []:
    field_base = base + field['suffix']
    restored = image_data.restored_image(field_base)
    if not restored:
      print(f"results: no restored image for {field_base}; skipping its FITS export.")
      continue
    try:
      ct.exportfits(imagename=restored, overwrite=True,
                    fitsimage=str(Path(results_dir) / f"{name}.{field['label']}.fits"))
      if field['label'] == TARGET_LABEL:
        pb = field_base + ('.pb.tt0' if restored.endswith('.tt0') else '.pb')
        ct.impbcor(imagename=restored, pbimage=pb, outfile=field_base + '.pbcorimage',
                   overwrite=True)
        ct.exportfits(imagename=field_base + '.pbcorimage', overwrite=True,
                      fitsimage=str(Path(results_dir) / f"{name}.{field['label']}.pbcor.fits"))
    except Exception as e:
      print(f"results: FITS export of {field_base} failed: {e}")


#------------------------------------------------------------------- the search

def _plan(options, cell_arcsec, beam_arcsec):
  vis = options.calibrated_filename + '.ms'
  freq_ghz, frame = _observing(vis), 'J2000'
  fwhm = PB_FWHM_ARCMIN_GHZ / freq_ghz * 60  #arcsec
  nx, ny = _image_size(options.image_size)
  main_half = (nx * cell_arcsec / 2, ny * cell_arcsec / 2)
  if min(main_half) >= PB_EDGE_FWHM * fwhm:
    _say(f"outlier fields: none needed; the main image already reaches "
         f"{PB_EDGE_FWHM * fwhm / 60:.1f}', where tclean stops cleaning")
    return []

  base, cell_s = _sweep(options, vis, fwhm, beam_arcsec)
  model, cs = _read(base + '.model')
  pb, _ = _read(base + '.pb')
  beam = image_data.beam_from_header(image_data.read_header(base + '.image'))
  beam_px = (beam['major_arcsec'] if beam else 3 * cell_s) / cell_s
  ref = tuple(cs.referencepixel()['numeric'][:2])
  main_box = _box_around(ref, main_half[0] / cell_s, main_half[1] / cell_s)
  min_half = OUTLIER_FIELD_MIN_PX / 2 * cell_arcsec / cell_s
  edge = _beam_edge(pb, ref, PB_LIMIT) * cell_s / 60  #arcmin

  islands = _islands(model, OUTLIER_MERGE_BEAMS * beam_px)
  floor = max([OUTLIER_MIN_APPARENT_JY]
              + [i['flux'] / OUTLIER_SWEEP_DYNAMIC_RANGE for i in islands])
  entries, beyond = _entries(islands, pb, main_box, floor, OUTLIER_MARGIN_BEAMS * beam_px,
                             min_half)
  target = _target_entry(options, cs, frame, pb, ref, main_box, cell_s, edge,
                         OUTLIER_TARGET_FIELD_PX / 2 * cell_arcsec / cell_s, min_half)
  entries = _merge(entries + ([target] if target else []))
  if target and not any(e['target'] and not _overlaps(e['box'], main_box) for e in entries):
    _say("the target's field merged into one touching the main image; enlarge image_size")
  entries = [e for e in entries if not _overlaps(e['box'], main_box)]
  outliers = sorted((e for e in entries if not e['target']), key=lambda e: -e['flux'])
  if len(outliers) > OUTLIER_MAX_FIELDS:
    _say(f"outlier fields: keeping the {OUTLIER_MAX_FIELDS} brightest of {len(outliers)}")
  numbered = ([(None, e) for e in entries if e['target']]
              + list(enumerate(outliers[:OUTLIER_MAX_FIELDS], 1)))

  fields = [_field(e, n, cs, frame, ref, cell_s, cell_arcsec) for n, e in numbered]
  _report(fields, [(math.dist((i['x'], i['y']), ref) * cell_s / 60, i['flux']) for i in beyond],
          edge, floor)
  return fields


def _read(path):
  '''(first plane as a 2-D array, coordinate system) of a CASA image.'''
  ia = casatools.image()
  ia.open(path)
  try:
    return ia.getchunk()[:, :, 0, 0], ia.coordsys()
  finally:
    ia.close()


def _observing(vis):
  '''Mean frequency of the calibrated MS, in GHz.'''
  msmd = casatools.msmetadata()
  msmd.open(vis)
  try:
    freq = float(np.mean([msmd.meanfreq(s) for s in range(msmd.nspw())]))
  finally:
    msmd.close()
  return freq / 1e9


def _sweep(options, vis, fwhm, beam_arcsec):
  '''Clean out to OUTLIER_SWEEP_RADIUS_FWHM, tapered to 3 pixels a beam, down to
  OUTLIER_MIN_APPARENT_JY. Writes no model column. Returns (image base, cell in arcsec).'''
  base = options.image_filename + OUTLIER_SWEEP_SUFFIX
  for path in sorted(Path().glob(base + '.*')):
    ct.rmtables(str(path)) if path.is_dir() else path.unlink()
  cell = 2 * OUTLIER_SWEEP_RADIUS_FWHM * fwhm / OUTLIER_SWEEP_IMSIZE
  taper = [f"{3 * cell:.3f}arcsec"] if (beam_arcsec or 0) < 3 * cell else []
  _say(f"outlier search: {OUTLIER_SWEEP_IMSIZE} px at {cell:.2f}\" out to "
       f"{OUTLIER_SWEEP_RADIUS_FWHM:g} x the {fwhm / 60:.1f}' primary-beam FWHM"
       + (f", tapered to {taper[0]}" if taper else ''))
  ct.tclean(vis=vis, imagename=base, imsize=[OUTLIER_SWEEP_IMSIZE] * 2, cell=f"{cell:.4f}arcsec",
            specmode='mfs', gridder='standard', deconvolver='hogbom', weighting='natural',
            uvtaper=taper, niter=OUTLIER_SWEEP_NITER, threshold=f"{OUTLIER_MIN_APPARENT_JY}Jy",
            nsigma=OUTLIER_SWEEP_NSIGMA, pblimit=CLEAN_PBLIMIT, interactive=False,
            savemodel='none', phasecenter=getattr(options, 'phasecenter', ''))
  return base, cell


def _target_entry(options, cs, frame, pb, ref, main_box, cell_s, edge, half, min_half):
  '''A box for the target when it lies outside the main image where tclean will clean;
  None (with the reason said) otherwise. edge is that limit's radius, in arcmin.'''
  try:
    ra, dec = float(options.source_ra), float(options.source_decl)
  except (AttributeError, TypeError, ValueError):
    return None
  me = casatools.measures()
  direction = me.measure(me.direction('J2000', f"{ra}deg", f"{dec}deg"), frame)
  me.done()
  world = cs.referencevalue(format='n')['numeric']
  world[0], world[1] = direction['m0']['value'], direction['m1']['value']
  at = tuple(cs.topixel(world)['numeric'][:2])
  gap = _gap(at, main_box)
  offset = math.dist(at, ref) * cell_s / 60
  if gap <= 0:
    print(f"target is {offset:.1f}' out, inside the main image: no target field")
    return None
  if _beam_at(pb, at) <= PB_LIMIT:
    _say(f"target is {offset:.1f}' out, past the {edge:.1f}' where tclean stops cleaning: "
         f"no target field")
    return None
  half = min(half, gap - 1)
  if half < min_half:
    _say(f"target is {offset:.1f}' out, just past the main image's edge: "
         f"enlarge image_size to include it")
    return None
  return {'box': _box_around(at, half, half), 'flux': 0.0, 'target': True, 'at': at}


def _field(entry, index, cs, frame, ref, cell_s, cell_arcsec):
  '''An entry's box as a tclean field that stays inside it. A box wider than
  OUTLIER_FIELD_MAX_PX is cut down around its flux centroid (or the target).'''
  x0, x1, y0, y1 = entry['box']
  size = max((x1 - x0) * cell_s / cell_arcsec, OUTLIER_FIELD_MIN_PX)
  centre = ((x0 + x1) / 2, (y0 + y1) / 2)
  if size > OUTLIER_FIELD_MAX_PX:
    size = OUTLIER_FIELD_MAX_PX
    half = size / 2 * cell_arcsec / cell_s
    centre = (min(max(entry['at'][0], x0 + half), x1 - half),
              min(max(entry['at'][1], y0 + half), y1 - half))
    _say(f"outlier field at {math.dist(centre, ref) * cell_s / 60:.1f}' capped at "
         f"{OUTLIER_FIELD_MAX_PX} px; the source extends past it")
  ra, dec = cs.toworld([centre[0], centre[1], 0, 0], 'n')['numeric'][:2]
  label = TARGET_LABEL if entry['target'] else f"{OUTLIER_FIELD_SUFFIX.lstrip('_')}{index:02d}"
  return {'label': label, 'suffix': '_' + label, 'frame': frame,
          'ra_rad': float(ra), 'dec_rad': float(dec),
          'imsize': _fft_size(size),
          'apparent_jy': entry['flux'] or None,
          'offset_arcmin': round(math.dist(centre, ref) * cell_s / 60, 2)}


def _fft_size(size):
  '''The largest image size <= size that tclean grids efficiently: rounding up could
  push a field into its neighbour.'''
  su = casatools.synthesisutils()
  n = int(size)
  while su.getOptimumSize(n) > n:
    n -= 1
  return n


def _report(fields, beyond, edge, floor):
  outliers = [f for f in fields if f['label'] != TARGET_LABEL]
  has_target = len(outliers) < len(fields)
  summary = (f"{len(outliers)} outlier field(s) above {floor * 1e3:.3g} mJy apparent"
             + (", plus the target's field" if has_target else ''))
  _say("outlier fields: " + summary)
  for f in fields:
    flux = f"{f['apparent_jy'] * 1e3:8.1f} mJy" if f['apparent_jy'] else '  (target)  '
    print(f"    {f['label']:<12} {f['offset_arcmin']:6.1f}'  {flux}  {f['imsize']} px")
  if beyond:
    _say(f"{len(beyond)} source(s) above the floor lie at or past the {edge:.1f}' where "
         f"tclean stops cleaning, so get no field; their sidelobes stay in: "
         + ', '.join(f"{off:.1f}' ({flux * 1e3:.0f} mJy)" for off, flux in sorted(beyond)[:5]))
  run_log.note('IMAGING', 'Outlier fields', summary)


def _say(text):
  print(text)
  run_log.event(text)


#------------------------------------------------------------- pixel geometry
#Boxes are (x0, x1, y0, y1) in search-image pixels, x first as CASA orders the axes.

def _islands(model, merge_px):
  '''Groups of positive clean components within merge_px of one another, as
  [{'x', 'y', 'flux', 'box'}]: flux-weighted centre, summed flux, component extent.'''
  comps = model > 0
  if not comps.any():
    return []
  r = max(1, int(math.ceil(merge_px)))
  dx, dy = np.ogrid[-r:r + 1, -r:r + 1]
  labels, _ = ndimage.label(ndimage.binary_dilation(comps, structure=dx**2 + dy**2 <= r * r))
  xs, ys = np.nonzero(comps)
  flux, lab = model[comps], labels[comps]
  islands = []
  for k in np.unique(lab):
    sel = lab == k
    w, x, y = flux[sel], xs[sel], ys[sel]
    islands.append({'x': float((x * w).sum() / w.sum()), 'y': float((y * w).sum() / w.sum()),
                    'flux': float(w.sum()),
                    'box': (float(x.min()), float(x.max()), float(y.min()), float(y.max()))})
  return islands


def _entries(islands, pb, main_box, floor, margin, min_half):
  '''Field boxes for the islands at or above floor that lie outside the main image, as
  entries, plus the islands sitting where pb is at or under PB_LIMIT (no field possible).'''
  entries, beyond = [], []
  for island in islands:
    if island['flux'] < floor:
      continue
    at = (island['x'], island['y'])
    if _beam_at(pb, at) <= PB_LIMIT:
      beyond.append(island)
      continue
    box = _square(_pad(island['box'], margin), min_half)
    if not _overlaps(box, main_box):  #inside the main image, or straddling its edge
      entries.append({'box': box, 'flux': island['flux'], 'target': False, 'at': at})
  return entries, beyond


def _beam_at(pb, point):
  '''pb at point: the lowest of its pixel and the eight around it, so a field's own grid
  can't land under it. 0 at or past the image's edge.'''
  x, y = int(round(point[0])), int(round(point[1]))
  if not (1 <= x < pb.shape[0] - 1 and 1 <= y < pb.shape[1] - 1):
    return 0.0
  return float(pb[x - 1:x + 2, y - 1:y + 2].min())


def _beam_edge(pb, centre, limit):
  '''Distance in pixels from centre to the farthest pixel where pb is above limit.'''
  x, y = np.nonzero(pb > limit)
  return float(np.hypot(x - centre[0], y - centre[1]).max()) if x.size else 0.0


def _box_around(centre, half_x, half_y):
  return (centre[0] - half_x, centre[0] + half_x, centre[1] - half_y, centre[1] + half_y)


def _pad(box, margin):
  return (box[0] - margin, box[1] + margin, box[2] - margin, box[3] + margin)


def _square(box, min_half=0.0):
  '''The square sharing box's centre that covers it, at least min_half across each way.'''
  half = max((box[1] - box[0]) / 2, (box[3] - box[2]) / 2, min_half)
  return _box_around(((box[0] + box[1]) / 2, (box[2] + box[3]) / 2), half, half)


def _overlaps(a, b):
  return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def _gap(point, box):
  '''How far point lies outside box, per axis (the larger); <= 0 inside it. A square of
  half-width under this, centred on point, clears the box.'''
  return max(box[0] - point[0], point[0] - box[1], box[2] - point[1], point[1] - box[3])


def _merge(entries):
  '''Union overlapping entries until none overlap: tclean double-counts flux that two
  fields share. Fluxes add; 'at' is the target if either is it, else the flux centroid.'''
  entries = [dict(e) for e in entries]
  merged = True
  while merged:
    merged = False
    for i in range(len(entries)):
      for j in range(i + 1, len(entries)):
        a, b = entries[i], entries[j]
        if _overlaps(a['box'], b['box']):
          union = (min(a['box'][0], b['box'][0]), max(a['box'][1], b['box'][1]),
                   min(a['box'][2], b['box'][2]), max(a['box'][3], b['box'][3]))
          entries[i] = {'box': _square(union), 'flux': a['flux'] + b['flux'],
                        'target': a['target'] or b['target'], 'at': _joined_at(a, b)}
          del entries[j]
          merged = True
          break
      if merged:
        break
  return entries


def _joined_at(a, b):
  for e in (a, b):
    if e['target']:
      return e['at']
  total = a['flux'] + b['flux']
  if total <= 0:
    return a['at']
  return tuple((pa * a['flux'] + pb * b['flux']) / total for pa, pb in zip(a['at'], b['at']))


def _image_size(size):
  if isinstance(size, (int, float)):
    return int(size), int(size)
  return int(size[0]), int(size[-1])
