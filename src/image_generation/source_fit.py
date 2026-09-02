"""2D Gaussian fit of the science target, and the archived record of it.

Drives casatasks.imfit on the run's best image and reads the fit out of the
task's return value, which carries per-parameter errors and the deconvolved
source size -- i.e. whether the source is actually resolved, rather than just
how big the beam made it look.

The measurements this fit needs (off-source RMS, restoring beam) come from
classes.image_data.Image: that module measures, this one fits and persists.

imfit is deliberately NOT in call_recorder._RECORDED_TASKS, for the same reason
imstat is not: it measures rather than transforms, so replay.py has no decision
for it to drive.
"""
import json
import shutil
from pathlib import Path
from typing import Any, cast

import astropy.units as u
import casatasks as ct

from classes.image_data import (beam_from_header, convert_unit, first_value,
                                header_value, image_shape, imstat_dict,
                                pixel_scale_arcsec, to_arcsec)
from classes.constants import (FIT_BOX_BEAMS, FIT_BOX_MAX_IMAGE_FRACTION,
                               FIT_BOX_MIN_PIXELS)
from pre_calibration.options_class import Options

#see image_data: astropy's unit attributes are built dynamically, so u.Unit() is
#used instead of u.deg / u.hourangle for the benefit of static checkers.
DEGREE = u.Unit('deg')
HOURANGLE = u.Unit('hourangle')
GIGAHERTZ = u.Unit('GHz')


def fit_best_image(options: Options, image):
  '''Fit the run's best image and archive the result.

  `image` is the winning image_data.Image, which already knows its own path,
  beam and off-source noise. Writes <name>.fit.json and imfit's log into the
  results folder, prints a summary, and returns the record -- or None if there
  was nothing to fit. Keyed, not positional, so adding or reordering a field
  cannot shift the archived values.
  '''
  if image is None or not image.path:
    print("Source fit skipped: no restored image found for the best cycle.")
    return None

  header = image.header()
  #the off-source RMS sets imfit's reported uncertainties, and is only meaningful
  #if the noise is uniform across the fit region -- which is why the fit runs on
  #the flat-noise restored image and not the pbcor one, whose noise rises with radius
  rms = image.off_source_rms()
  box = peak_fit_box(image, header)

  results_dir = Path(getattr(options, 'results_dir', '') or '.')
  name = getattr(options, 'results_name', '') or Path(image.path).name.split('.')[0]

  fit = fit_source(image.path, rms=rms, box=box,
                   logfile=results_dir / f"{name}.imfit.log",
                   residual=results_dir / f"{name}.imfit.residual")
  if fit is None:
    return None
  #imfit only reports a frequency when the component carries a spectrum; the image
  #header always has one, so fall back to it rather than archiving a null
  if fit.get('frequency_ghz') is None:
    fit['frequency_ghz'] = _to_ghz(_header_frequency(header))

  record = {**image.measurements(), 'fit_box': box or '(whole image)', **fit}
  #hand the record to Options so the run log can report it without re-fitting
  options.fit_record = record
  try:
    (results_dir / f"{name}.fit.json").write_text(
      json.dumps(record, indent=2, default=str))
    print(f"Wrote source fit: {results_dir / f'{name}.fit.json'}")
  except Exception as exc:
    print(f"source_fit: could not write {name}.fit.json: {exc}")
  print_summary(record)
  return record


def peak_fit_box(image, header):
  '''An imfit box centred on the image peak: half-side FIT_BOX_BEAMS synthesized
  beams, floored at FIT_BOX_MIN_PIXELS, capped at FIT_BOX_MAX_IMAGE_FRACTION of the
  image, and clamped to its bounds.

  Bounding the fit keeps the single component on the target rather than letting
  it wander onto a brighter field source. The cap matters because the box is
  sized in beams: on an over-sampled image an uncapped box grows back to the
  whole frame. Returns '' (fit everything) when the peak or geometry is unknown.
  '''
  shape, peak = image_shape(header), image.peak_pixel()
  if not shape or not peak:
    return ''
  nx, ny = shape
  half = FIT_BOX_MIN_PIXELS
  beam, cell = beam_from_header(header), pixel_scale_arcsec(header)
  if beam and cell and cell > 0:
    half = max(FIT_BOX_MIN_PIXELS, int(FIT_BOX_BEAMS * beam['major_arcsec'] / cell))
  half = min(half, int(min(nx, ny) * FIT_BOX_MAX_IMAGE_FRACTION))
  peak_x, peak_y = peak
  return (f"{max(0, peak_x - half)},{max(0, peak_y - half)},"
          f"{min(nx - 1, peak_x + half)},{min(ny - 1, peak_y + half)}")


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
  record['convolved_size'] = _axes(shape)

  #deconvolved = beam removed, i.e. the source's intrinsic size
  deconvolved = (result.get('deconvolved') or {}).get('component0') or {}
  record['deconvolved_size'] = _axes(deconvolved.get('shape'))
  is_point = deconvolved.get('ispoint', component.get('ispoint'))
  record['is_point_source'] = bool(is_point) if is_point is not None else None
  return record


def print_summary(record):
  '''One human-readable block at the end of a run, to stdout and the CASA log.'''
  lines = ["Source fit: converged" if record.get('converged') else
           "Source fit: DID NOT CONVERGE (values below are unreliable)"]
  rms = record.get('rms_jy_per_beam')
  if rms:
    lines.append(f"  off-source RMS  : {rms:.3e} Jy/beam ({record.get('rms_method')})")
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
  text = "\n".join(lines)
  print(text)
  try:
    ct.casalog.post(text, priority='INFO')
  except Exception:
    pass


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
