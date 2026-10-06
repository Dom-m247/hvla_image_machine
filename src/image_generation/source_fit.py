"""The science target's measurement on the best image, and the archived record of it.

The target is measured where the catalogue puts it (NED, J2000), not wherever the
image happens to peak: a brighter field source, a sidelobe or a noise streak would
otherwise be fitted and reported as the target. Around that position:

  detection -- the peak within DETECTION_SEARCH_BEAMS of the target, in units of
               the off-source rms. At or above options.detection_sigma (default
               DETECTION_SIGMA) the target is detected; below it the record carries
               an upper limit of that many rms instead of a flux.
  fit       -- a 2D Gaussian (casatasks.imfit) in a box around the target whenever
               the peak reaches FIT_MIN_SNR, whose return value carries per-parameter
               errors and the deconvolved size -- whether the source is resolved,
               rather than how big the beam made it look.

Without a catalogue position the fit falls back to the image peak, and the record
says so. Positions are converted with CASA's measures throughout (image_data), never
through an exported FITS header.

The measurements this needs (off-source RMS, restoring beam) come from
classes.image_data.Image: that module measures, this one fits and persists.

imfit is deliberately NOT in call_recorder._RECORDED_TASKS, for the same reason
imstat is not: it measures rather than transforms, so replay.py has no decision
for it to drive.
"""
import json
import math
import shutil
from pathlib import Path
from typing import Any, cast

import astropy.units as u
import casatasks as ct

from classes.image_data import (beam_from_header, convert_unit, field_centre_j2000,
                                first_value, header_value, image_shape, imstat_dict,
                                pb_image, pixel_scale_arcsec, pixel_value, region_peak,
                                separation_arcsec, sky_to_pixel, to_arcsec)
from classes.constants import (DETECTION_SEARCH_BEAMS, DETECTION_SIGMA, FIT_BOX_BEAMS,
                               FIT_BOX_MAX_IMAGE_FRACTION, FIT_BOX_MIN_PIXELS,
                               FIT_MIN_SNR, FIT_TARGET_BOX_BEAMS, NOISE_RATIO_WARN)
from pre_calibration.options_class import Options

#see image_data: astropy's unit attributes are built dynamically, so u.Unit() is
#used instead of u.deg / u.hourangle for the benefit of static checkers.
DEGREE = u.Unit('deg')
HOURANGLE = u.Unit('hourangle')
GIGAHERTZ = u.Unit('GHz')

_ned_asked = set()   #names already looked up this run, so NED is asked once


def fit_best_image(options: Options, image):
  '''Measure the target on the run's best image and archive the result.

  `image` is the winning image_data.Image, which already knows its own path,
  beam and off-source noise. Writes <name>.fit.json and imfit's log into the
  results folder, prints a summary, and returns the record -- or None if there
  was nothing to measure. Keyed, not positional, so adding or reordering a field
  cannot shift the archived values.
  '''
  if image is None or not image.path:
    print("Source fit skipped: no restored image found for the best cycle.")
    return None

  header = image.header()
  #the off-source RMS sets the detection threshold and imfit's reported
  #uncertainties, and is only meaningful if the noise is uniform across the image --
  #which is why everything here runs on the flat-noise restored image and not the
  #pbcor one, whose noise rises with radius
  rms = image.off_source_rms()
  results_dir = Path(getattr(options, 'results_dir', '') or '.')
  name = getattr(options, 'results_name', '') or Path(image.path).name.split('.')[0]
  fit_files = {'logfile': results_dir / f"{name}.imfit.log",
               'residual': results_dir / f"{name}.imfit.residual"}

  record = {**image.measurements(), **_noise_check(options, rms),
            'flux_scale': flux_scale(options)}
  target = locate_target(options, image, header)
  if target and target['in_image']:
    detection = detect(image, target, rms, header, _sigma(options))
    record.update(target=target, detection=detection, fit_centre='target')
    if (detection['snr'] or 0) >= FIT_MIN_SNR:
      box = _box_around(target['pixel'], header, FIT_TARGET_BOX_BEAMS)
      fit = fit_source(image.path, rms=rms, box=box, **fit_files) or {}
      record.update(fit_box=box or '(whole image)', **fit)
      record['offset_from_target_arcsec'] = _offset_arcsec(fit, target, header)
    else:
      #a Gaussian on noise would only invent a source; the upper limit is the result
      record.update(fit_box='', converged=None)
  else:
    #no catalogue position (or it falls off the image): the old behaviour, fitting
    #whatever is brightest -- said plainly in the record and the summary
    if target:
      record['target'] = target
    box = _box_around(image.peak_pixel(), header, FIT_BOX_BEAMS)
    fit = fit_source(image.path, rms=rms, box=box, **fit_files)
    if fit is None and not target:
      return None
    record.update(fit_centre='image peak', fit_box=box or '(whole image)', **(fit or {}))
  #imfit only reports a frequency when the component carries a spectrum; the image
  #header always has one, so fall back to it rather than archiving a null
  if record.get('frequency_ghz') is None:
    record['frequency_ghz'] = _to_ghz(_header_frequency(header))

  #hand the record to Options so the run log can report it without re-measuring
  options.fit_record = record
  try:
    (results_dir / f"{name}.fit.json").write_text(
      json.dumps(record, indent=2, default=str))
    print(f"Wrote source fit: {results_dir / f'{name}.fit.json'}")
  except Exception as exc:
    print(f"source_fit: could not write {name}.fit.json: {exc}")
  print_summary(record)
  return record


def target_position(options):
  '''The science target's J2000 position as (ra_deg, dec_deg), or None.

  NED's position, which the CLI, the GUI's source check, the archive search and
  every harness run carry as source_ra/source_decl. A run without one (an older
  import.json, a GUI source never checked) asks NED once here and keeps the answer
  on options, so the import.json this run writes carries it for a replay.'''
  ra = _float(getattr(options, 'source_ra', ''))
  dec = _float(getattr(options, 'source_decl', ''))
  if ra is not None and dec is not None:
    return ra % 360.0, dec
  name = getattr(options, 'search_alias', '') or getattr(options, 'source', '')
  if not name or name in _ned_asked:
    return None
  _ned_asked.add(name)
  from API_integrations.NED import NED_API   #lazy: astroquery is slow to import
  print(f"No catalogue position recorded for {name}; asking NED ...")
  resolved = NED_API.obj_exists(name)
  if not resolved:
    print(f"NED could not place {name}: the image is measured at its peak instead.")
    return None
  options.source_ra = resolved['ra_decl']['ra']
  options.source_decl = resolved['ra_decl']['decl']
  options.search_alias = options.search_alias or resolved['alias']
  return float(options.source_ra) % 360.0, float(options.source_decl)


def locate_target(options, image, header):
  '''Where the target falls on the image, or None without a catalogue position.

  Also records how far it sits from the pointing centre (both J2000, converted
  from the data by CASA) and the primary-beam response there, which corrects its
  flux for the attenuation of an off-axis pointing.'''
  position = target_position(options)
  if position is None:
    return None
  ra, dec = position
  pixel = sky_to_pixel(image.path, ra, dec)
  shape = image_shape(header)
  inside = bool(pixel and shape and 0 <= pixel[0] <= shape[0] - 1
                and 0 <= pixel[1] <= shape[1] - 1)
  pointing = field_centre_j2000(getattr(options, 'calibrated_filename', '') + '.ms')
  pb = pb_image(image.base)
  return {
    'ra_deg': ra, 'dec_deg': dec, 'position_from': 'NED',
    'pixel': [round(pixel[0], 2), round(pixel[1], 2)] if pixel else None,
    'in_image': inside,
    'pb_response': pixel_value(pb, *pixel) if (inside and pb and pixel) else None,
    'pointing_ra_deg': pointing[0] if pointing else None,
    'pointing_dec_deg': pointing[1] if pointing else None,
    'separation_from_pointing_arcsec': (separation_arcsec(ra, dec, pointing[0], pointing[1])
                                        if pointing else None),
  }


def detect(image, target, rms, header, sigma):
  '''Is the target there? The brightest pixel within DETECTION_SEARCH_BEAMS of its
  position, in units of the off-source rms, against `sigma`. A non-detection
  carries an upper limit of `sigma` rms (Jy/beam, before primary-beam correction).'''
  beam, cell = beam_from_header(header), pixel_scale_arcsec(header)
  radius_px = (DETECTION_SEARCH_BEAMS * beam['major_arcsec'] / cell
               if beam and cell else 3.0)
  x, y = target['pixel']
  peak, at = region_peak(image.path, x, y, radius_px)
  snr = peak / rms if (peak is not None and rms) else None
  detected = snr is not None and snr >= sigma
  return {
    'threshold_sigma': sigma,
    'search_radius_arcsec': radius_px * cell if cell else None,
    'peak_jy_per_beam': peak,
    'peak_pixel': list(at) if at else None,
    'value_at_target_jy_per_beam': pixel_value(image.path, x, y),
    'rms_jy_per_beam': rms,
    'snr': snr,
    'detected': detected,
    'upper_limit_jy_per_beam': None if detected or not rms else sigma * rms,
  }


def flux_scale(options):
  '''Where the run's flux scale came from: 'standard' (a Perley-Butler calibrator),
  'catalogue' (a calibrator's VLA-calibrator-list flux, with no standard calibrator
  observed -- good to perhaps 10-20%), or 'manual' (a flux the user typed).'''
  manual = getattr(options, 'flux_cal_manual', None) or {}
  calibrator = (getattr(getattr(options, 'flux_cal', None), 'listobs_name', '')
                or getattr(options, 'flux_cal_name', ''))
  if not manual:
    return {'origin': 'standard', 'calibrator': calibrator}
  return {'origin': manual.get('origin') or 'manual', 'calibrator': calibrator,
          'flux_jy': manual.get('flux'), 'quality': manual.get('quality')}


def _sigma(options):
  '''The run's detection threshold, in off-source rms.'''
  return _float(getattr(options, 'detection_sigma', None)) or DETECTION_SIGMA


def _noise_check(options, rms):
  '''Image noise against the noise of a Stokes V image made like it (see
  Cleaner.stokes_v_noise for what the ratio does and does not tell).'''
  stokes_v = getattr(options, 'stokes_v_rms', None)
  ratio = rms / stokes_v if (rms and stokes_v) else None
  return {'stokes_v_rms_jy_per_beam': stokes_v, 'noise_ratio': ratio,
          'noise_limited': None if ratio is None else ratio <= NOISE_RATIO_WARN}


def _offset_arcsec(fit, target, header):
  '''How far the fitted centroid sits from the target, arcsec (None if unknown).'''
  centroid, cell = fit.get('pixel'), pixel_scale_arcsec(header)
  if not (centroid and target.get('pixel') and cell):
    return None
  return math.hypot(centroid[0] - target['pixel'][0], centroid[1] - target['pixel'][1]) * cell


def _float(value):
  try:
    return float(value)
  except (TypeError, ValueError):
    return None


def _box_around(centre, header, beams):
  '''An imfit box centred on pixel `centre`: half-side `beams` synthesized beams,
  floored at FIT_BOX_MIN_PIXELS, capped at FIT_BOX_MAX_IMAGE_FRACTION of the image,
  and clamped to its bounds.

  Bounding the fit keeps the single component on the source it is centred on rather
  than letting it wander onto a brighter field source. The cap matters because the
  box is sized in beams: on an over-sampled image an uncapped box grows back to the
  whole frame. Returns '' (fit everything) when the centre or geometry is unknown.
  '''
  shape = image_shape(header)
  if not shape or not centre:
    return ''
  nx, ny = shape
  half = FIT_BOX_MIN_PIXELS
  beam, cell = beam_from_header(header), pixel_scale_arcsec(header)
  if beam and cell and cell > 0:
    half = max(FIT_BOX_MIN_PIXELS, int(beams * beam['major_arcsec'] / cell))
  half = min(half, int(min(nx, ny) * FIT_BOX_MAX_IMAGE_FRACTION))
  x, y = int(round(centre[0])), int(round(centre[1]))
  return (f"{max(0, x - half)},{max(0, y - half)},"
          f"{min(nx - 1, x + half)},{min(ny - 1, y + half)}")


def fit_source(image, rms=None, box='', logfile=None, residual=None) -> dict[str, Any] | None:
  '''Fit one 2D Gaussian; return its parameters as plain Python.

  residual : path for imfit's residual image. When given it is written and its
             RMS measured -- the goodness-of-fit number. Close to the off-source
             RMS means the Gaussian absorbed the source; much larger means real
             structure was left behind.

  Returns None only if imfit itself raised. A fit that ran without converging
  comes back with converged=False: a result to archive, not a crash.
  '''
  kwargs = {'imagename': image}
  if box:
    kwargs['box'] = box
  if rms:
    kwargs['rms'] = float(rms)
  if logfile:
    #append=False so a re-run replaces the log rather than growing it
    kwargs.update(logfile=str(logfile), append=False)
  if residual:
    #imfit won't overwrite an existing residual. Removed with shutil rather than
    #ct.rmtables so this analysis artifact doesn't show up as a step in replay.py.
    shutil.rmtree(residual, ignore_errors=True)
    kwargs['residual'] = str(residual)
  try:
    result = ct.imfit(**kwargs)
  except Exception as exc:
    print(f"source_fit: imfit failed on {image}: {exc}")
    return None
  if not result:
    return None

  record: dict[str, Any] = {'converged': bool(first_value(result.get('converged')))}
  if residual:
    record['residual_rms_jy_per_beam'] = _residual_rms(residual)
  component = (result.get('results') or {}).get('component0') or {}
  if not component:
    return record

  shape = component.get('shape') or {}
  record['peak_flux'] = _quantity(component.get('peak'))
  record['integrated_flux'] = _quantity(component.get('flux'))
  record['frequency_ghz'] = _frequency_ghz(component)
  record['position'] = _direction(shape.get('direction'))
  #the centroid in pixels, which is frame-free -- how far the fit sits from the
  #target is measured on it rather than on sky positions in whichever frame
  centroid = component.get('pixelcoords')
  record['pixel'] = ([round(float(centroid[0]), 2), round(float(centroid[1]), 2)]
                     if centroid is not None and len(centroid) >= 2 else None)
  record['convolved_size'] = _axes(shape)

  #deconvolved = beam removed, i.e. the source's intrinsic size
  deconvolved = (result.get('deconvolved') or {}).get('component0') or {}
  record['deconvolved_size'] = _axes(deconvolved.get('shape'))
  is_point = deconvolved.get('ispoint', component.get('ispoint'))
  record['is_point_source'] = bool(is_point) if is_point is not None else None
  return record


def print_summary(record):
  '''One human-readable block at the end of a run, to stdout and the CASA log.'''
  lines = _target_lines(record)
  scale = record.get('flux_scale') or {}
  if scale.get('origin') == 'catalogue':
    lines.append(f"  FLUX SCALE FROM CATALOGUE: {scale.get('calibrator')} at {scale.get('flux_jy'):g} Jy "
                 f"(quality {scale.get('quality') or '?'}); absolute fluxes uncertain by 10-20% or more")
  if record.get('converged') is None:
    lines.append("Source fit: not attempted (no source at the target)")
  else:
    lines.append("Source fit: converged" if record.get('converged') else
                 "Source fit: DID NOT CONVERGE (values below are unreliable)")
  rms = record.get('rms_jy_per_beam')
  if rms:
    lines.append(f"  off-source RMS  : {rms:.3e} Jy/beam ({record.get('rms_method')})")
  if record.get('noise_ratio'):
    flag = '' if record.get('noise_limited') else (
      f"  <-- above {NOISE_RATIO_WARN:g}x: Stokes I limited by dynamic range/calibration")
    lines.append(f"  Stokes V noise  : {record['stokes_v_rms_jy_per_beam']:.3e} Jy/beam "
                 f"(Stokes I noise is {record['noise_ratio']:.2f}x that){flag}")
  beam = record.get('beam')
  if beam:
    lines.append(f"  restoring beam  : {beam['major_arcsec']:.3g} x "
                 f"{beam['minor_arcsec']:.3g} arcsec @ "
                 f"{_number(beam['position_angle_deg'])} deg")
  frequency = record.get('frequency_ghz')
  if frequency:
    lines.append(f"  frequency       : {frequency:.6g} GHz")
  lines.append(f"  peak flux       : {_format_quantity(record.get('peak_flux'))}")
  lines.append(f"  integrated flux : {_format_quantity(record.get('integrated_flux'))}")
  residual = record.get('residual_rms_jy_per_beam')
  if residual:
    lines.append(f"  fit residual RMS: {residual:.3e} Jy/beam")
  position = record.get('position') or {}
  if position.get('ra'):
    lines.append(f"  position        : {position['ra']} {position.get('dec', '')}")
  size = record.get('deconvolved_size')
  if size and size.get('major_arcsec') is not None:
    resolved = "point source" if record.get('is_point_source') else "resolved"
    lines.append(f"  deconvolved     : {size['major_arcsec']:.3g} x "
                 f"{size['minor_arcsec']:.3g} arcsec @ "
                 f"{_number(size['position_angle_deg'])} deg ({resolved})")
  offset = record.get('offset_from_target_arcsec')
  if offset is not None:
    lines.append(f"  offset from target: {offset:.2f} arcsec")
  text = "\n".join(lines)
  print(text)
  try:
    ct.casalog.post(text, priority='INFO')
  except Exception:
    pass


def _target_lines(record):
  '''The detection verdict: where the target was measured, and what was found.'''
  target, detection = record.get('target') or {}, record.get('detection') or {}
  if not target:
    return ["Target: no catalogue position -- measured at the IMAGE PEAK, which may "
            "not be the target"]
  where = (f"Target (NED J2000 {target['ra_deg']:.5f} {target['dec_deg']:+.5f})")
  sep = target.get('separation_from_pointing_arcsec')
  if sep is not None:
    where += f", {sep:.1f}\" from the pointing centre"
  if target.get('pb_response'):
    where += f", primary-beam response {target['pb_response']:.2f}"
  lines = [where]
  if not target.get('in_image'):
    lines.append("  OUTSIDE THE IMAGE -- measured at the image peak instead, which is "
                 "not the target")
    return lines
  snr, sigma = detection.get('snr'), detection.get('threshold_sigma')
  peak = detection.get('peak_jy_per_beam')
  if snr is None or peak is None:
    lines.append("  could not measure the image at the target")
    return lines
  radius = detection.get('search_radius_arcsec')
  verdict = (f"DETECTED (>= {sigma:g} sigma)" if detection.get('detected')
             else f"NOT DETECTED (< {sigma:g} sigma); upper limit "
                  f"{detection['upper_limit_jy_per_beam']:.3e} Jy/beam")
  lines.append(f"  peak within {radius:.1f}\": {peak:.3e} Jy/beam = {snr:.1f} sigma -> {verdict}"
               if radius else f"  peak {peak:.3e} Jy/beam = {snr:.1f} sigma -> {verdict}")
  return lines


#---------------------------------------------------------------- imfit unpacking

def _quantity(quantity):
  '''A flux-like imfit entry -> {'value', 'error', 'unit'}, unit preserved.

  Keeping the unit attached is what removes 1.99's mJy/Jy guesswork, where a
  `janskify` flag set while parsing the peak flux was never reset and then
  divided an already-Jy integrated flux by 1000 on its way to the archive.
  '''
  if not isinstance(quantity, dict):
    return None
  return {'value': first_value(quantity.get('value')),
          'error': first_value(quantity.get('error')),
          'unit': quantity.get('unit')}


def _axes(shape):
  '''Gaussian axes from an imfit shape block: arcsec + degrees, or None.'''
  if not isinstance(shape, dict):
    return None
  major, minor = to_arcsec(shape.get('majoraxis')), to_arcsec(shape.get('minoraxis'))
  if major is None and minor is None:
    return None
  angle = shape.get('positionangle')
  return {'major_arcsec': major,
          'minor_arcsec': minor,
          'position_angle_deg': first_value(angle.get('value')
                                            if isinstance(angle, dict) else angle)}


def _direction(direction):
  '''Fitted position as sexagesimal RA/Dec plus decimal degrees.

  imfit reports the direction as CASA quantities (radians, by default). astropy
  formats them in the conventional style -- '03:26:15.8880 +34:22:38.884' rather
  than CASA's dot-separated, zero-padded '+034.22.38.884'. Degrees are kept
  alongside so the archived record stays machine-comparable.
  '''
  if not isinstance(direction, dict):
    return {}
  frame = direction.get('refer', '')
  ra_deg, dec_deg = _angle_deg(direction.get('m0')), _angle_deg(direction.get('m1'))
  if ra_deg is None or dec_deg is None:
    return {'frame': frame}
  ra_deg %= 360.0   #imfit hands RA back in -pi..pi; A2218's came out as -111 deg
  try:
    from astropy.coordinates import SkyCoord
    #astropy is untyped enough that .ra/.dec read as Optional; they're Angles here
    coord = cast(Any, SkyCoord(ra_deg * DEGREE, dec_deg * DEGREE))
    return {'ra': coord.ra.to_string(unit=HOURANGLE, sep=':', pad=True, precision=4),
            'dec': coord.dec.to_string(sep=':', pad=True, alwayssign=True, precision=3),
            'ra_deg': ra_deg, 'dec_deg': dec_deg, 'frame': frame}
  except Exception as exc:
    print(f"source_fit: could not format the fitted position ({exc}); keeping degrees.")
    return {'ra_deg': ra_deg, 'dec_deg': dec_deg, 'frame': frame}


def _residual_rms(residual):
  '''RMS of imfit's residual image -- how much the Gaussian failed to absorb.'''
  try:
    return first_value(imstat_dict(imagename=str(residual)).get('rms'))
  except Exception as exc:
    print(f"source_fit: could not measure the fit residual ({exc}).")
    return None


def _frequency_ghz(component):
  '''Observing frequency of the fitted component, in GHz.'''
  spectrum = component.get('spectrum') or {}
  frequency = (spectrum.get('frequency') or {}).get('m0')
  return _to_ghz(frequency)


def _header_frequency(header):
  '''Observing frequency from an image header, as a CASA-style quantity dict.'''
  restfreq = header_value(header, 'restfreq', 'reffreq', 'crval4')
  value = first_value(restfreq)   #usually a 1-element array of Hz
  if value is not None:
    return {'value': value, 'unit': 'Hz'}
  return restfreq if isinstance(restfreq, dict) else None


def _to_ghz(quantity):
  '''A CASA frequency quantity -> float GHz. An unmarked value is read as Hz.'''
  if not isinstance(quantity, dict):
    return None
  value, unit = first_value(quantity.get('value')), quantity.get('unit') or 'Hz'
  if value is None:
    return None
  try:
    return convert_unit(value, u.Unit(unit), GIGAHERTZ)
  except Exception as exc:
    print(f"source_fit: could not convert {value} {unit} to GHz ({exc}).")
    return None


def _angle_deg(quantity):
  '''A CASA angle quantity -> float degrees. imfit emits radians unless told
  otherwise, so an unmarked value is read as radians.'''
  if not isinstance(quantity, dict):
    return None
  value, unit = first_value(quantity.get('value')), quantity.get('unit') or 'rad'
  if value is None:
    return None
  try:
    return convert_unit(value, u.Unit(unit), DEGREE)
  except Exception as exc:
    print(f"source_fit: could not convert {value} {unit} to degrees ({exc}).")
    return None


def _number(value, fmt='.4g'):
  '''Format a possibly-None number for the summary.'''
  return format(value, fmt) if isinstance(value, (int, float)) else '?'


def _format_quantity(quantity):
  '''"0.123 +/- 0.002 Jy" from a _quantity() dict.'''
  if not quantity or quantity.get('value') is None:
    return "(not measured)"
  text = f"{quantity['value']:.6g}"
  if quantity.get('error'):
    text += f" +/- {quantity['error']:.3g}"
  return f"{text} {quantity.get('unit') or ''}".strip()
