"""Image measurement: what an imaging cycle produced, and how good it is.

`Image` wraps an imstat result and adds the measurements images are scored and
archived by:

  off_source_rms() -- noise measured AWAY from the source; whole-image RMS is
                      inflated by the source itself.
  beam()           -- restoring beam, read from the header rather than fitted.
  dynamic_range()  -- peak / off-source RMS, the self-cal figure of merit.

The fit that consumes these lives in image_generation/source_fit.py: this module
measures, that one fits and persists.

Best-effort throughout -- a measurement that cannot be made returns None rather
than raising, because none of it is allowed to lose a finished image.
"""
from pathlib import Path
from statistics import median
from typing import Any, cast

import astropy.units as u
import casatasks as ct

from classes.constants import (MAD_TO_SIGMA, RMS_CORNER_BOX_FRACTION,
                               RMS_EDGE_MARGIN_FRACTION)
from pre_calibration.options_class import Options

#astropy builds u.rad / u.arcsec dynamically at import, so a static checker can't
#see them; u.Unit() is a real class and resolves. Same objects either way.
RADIAN = u.Unit('rad')
ARCSEC = u.Unit('arcsec')


class Image:
  #imstat keys copied straight onto the object. maxpos (the peak's PIXEL position)
  #is what a fit box is centred on; maxposf is the same point formatted as world
  #coordinates, which is human-readable but not indexable.
  STAT_KEYS = ('blc', 'blcf', 'flux', 'max', 'maxpos', 'maxposf', 'mean',
               'medabsdevmed', 'median', 'min', 'minpos', 'minposf', 'npts',
               'q1', 'q3', 'quartile', 'rms', 'sigma', 'sum', 'sumsq', 'trc', 'trcf')

  #set dynamically from STAT_KEYS in __init__; declared here so the type checker
  #(and editor completion) knows them. imstat hands back numpy arrays of varying
  #dtype, so Any -- use the accessors below rather than indexing these directly.
  blc: Any
  blcf: Any
  flux: Any
  max: Any
  maxpos: Any
  maxposf: Any
  mean: Any
  medabsdevmed: Any
  median: Any
  min: Any
  minpos: Any
  minposf: Any
  npts: Any
  q1: Any
  q3: Any
  quartile: Any
  rms: Any
  sigma: Any
  sum: Any
  sumsq: Any
  trc: Any
  trcf: Any

  def __init__(self, options: Options, image_data, base=''):
    '''Wrap an imstat result.

    base : the cycle's filename base, so the object can find its own restored
           image for the header/noise measurements. Without it this is still a
           plain imstat holder.

    A missing imstat result leaves every field None rather than leaving the
    object with no attributes, so a failed measurement can't surface as an
    AttributeError three frames away.
    '''
    stats = image_data or {}
    for key in self.STAT_KEYS:
      setattr(self, key, stats.get(key))
    self.base = str(base or '')
    self.path = restored_image(self.base)
    self.rms_method = 'none'   #set by off_source_rms(); which estimator was used
    self._off_source_rms = None
    self._beam = None
    self._header = None

  #--------------------------------------------------------------- scalar access
  #imstat returns 1-element numpy arrays; these hand back plain floats so callers
  #stop writing image.max[0] / image.rms[0] and can't trip over a None result.

  def peak(self):
    '''Brightest pixel, Jy/beam.'''
    return first_value(self.max)

  def total_flux(self):
    '''Integrated flux over the image, Jy.'''
    return first_value(self.flux)

  def whole_image_rms(self):
    '''RMS over the whole image -- source-contaminated; prefer off_source_rms().'''
    return first_value(self.rms)

  def peak_pixel(self):
    '''(x, y) pixel position of the peak, or None.'''
    try:
      return int(self.maxpos[0]), int(self.maxpos[1])
    except (TypeError, IndexError, ValueError):
      return None

  #----------------------------------------------------------------- measurements

  def header(self):
    '''Cached imhead(mode='list') for this image ({} if unreadable).'''
    if self._header is None and self.path:
      self._header = read_header(self.path)
    return self._header or {}

  def beam(self):
    '''Restoring beam as {'major_arcsec', 'minor_arcsec', 'position_angle_deg'},
    or None if the image carries no single restoring beam.'''
    if self._beam is None and self.path:
      self._beam = beam_from_header(self.header())
    return self._beam

  def off_source_rms(self):
    '''Background RMS in Jy/beam, measured away from the source (or None).

    Cached; the estimator actually used is recorded on self.rms_method, so the
    archived record can say how the number was obtained.
    '''
    if self._off_source_rms is None and self.path:
      self._off_source_rms, self.rms_method = measure_off_source_rms(self.path)
    return self._off_source_rms

  def dynamic_range(self):
    '''Self-cal figure of merit: peak / off-source background RMS.

    As self-cal improves, the peak rises and the sidelobes fall, so this rises.
    Measured off-source rather than over the whole image so that a brightening
    source can't inflate its own noise denominator and mask a real improvement.
    Falls back to the whole-image RMS when the background can't be measured, so a
    cycle is always scored; 0.0 when neither RMS is usable.
    '''
    peak = self.peak()
    rms = self.off_source_rms() or self.whole_image_rms()
    if peak is None or not rms or rms <= 0:
      return 0.0
    return peak / rms

  def measurements(self):
    '''The measured (not fitted) quantities, as JSON-safe plain Python. Forms the
    top of the archived fit record in source_fit.'''
    return {
      'image': self.path,
      'peak_jy_per_beam': self.peak(),
      'image_flux_jy': self.total_flux(),
      'rms_jy_per_beam': self.off_source_rms(),
      'rms_method': self.rms_method,
      'dynamic_range': self.dynamic_range(),
      'beam': self.beam(),
    }


#------------------------------------------------------------------ image lookup

def restored_image(base):
  '''The restored image an imaging cycle wrote: <base>.image.tt0 (mtmfs/nterms)
  or <base>.image (every other deconvolver), whichever exists. '' if neither.'''
  for ext in ('.image.tt0', '.image'):
    if base and Path(str(base) + ext).is_dir():
      return str(base) + ext
  return ''


#----------------------------------------------------------------- header access

def read_header(image):
  '''imhead(mode='list') -- shape, pixel scale and beam in a single read.'''
  try:
    return ct.imhead(imagename=image, mode='list') or {}
  except Exception as exc:
    print(f"image_data: could not read header of {image}: {exc}")
    return {}


def image_shape(hdr):
  '''(nx, ny) in pixels, or None.'''
  shape = (hdr or {}).get('shape')
  if shape is None:
    return None
  try:
    return int(shape[0]), int(shape[1])
  except (TypeError, IndexError, ValueError):
    return None


def pixel_scale_arcsec(hdr):
  '''Absolute pixel size in arcsec from cdelt2, or None. cdelt2 comes back as a
  bare float in radians in some CASA versions and as a quantity dict in others;
  the bare form carries no unit, so radians is the documented CASA convention.'''
  cdelt = (hdr or {}).get('cdelt2')
  radians = first_value(cdelt)
  if radians is not None:
    return abs(convert_unit(radians, RADIAN, ARCSEC))
  arcsec = to_arcsec(cdelt)
  return abs(arcsec) if arcsec else None


def beam_from_header(hdr):
  '''Restoring beam from a header, or None when there isn't a single one (a
  per-plane beam set has no scalar beam).

  imhead(mode='list') names these beammajor/beamminor/beampa; the FITS-style
  bmaj/bmin/bpa turn up on other paths, so both spellings are accepted.'''
  if not hdr:
    return None
  major = to_arcsec(header_value(hdr, 'beammajor', 'bmaj'))
  minor = to_arcsec(header_value(hdr, 'beamminor', 'bmin'))
  if major is None or minor is None:
    return None
  angle = header_value(hdr, 'beampa', 'bpa')
  return {'major_arcsec': major,
          'minor_arcsec': minor,
          'position_angle_deg': first_value(angle.get('value')
                                            if isinstance(angle, dict) else angle)}


def header_value(hdr, *keys):
  '''First of `keys` actually present in the header -- CASA spells the same
  quantity differently depending on version and code path.'''
  for key in keys:
    if key in (hdr or {}):
      return hdr[key]
  return None


#--------------------------------------------------------------- off-source noise

def measure_off_source_rms(image):
  '''Background RMS as (value, method).

  Median of four corner boxes, inset from the edge where gridding artifacts
  live, so one corner holding a sidelobe can't drag the estimate. Needs at least
  two usable corners.

  Falls back to sigma = 1.4826 * MAD over the whole image, which a compact
  bright source barely moves, for images too small for corner boxes.
  (None, 'none') if neither works.
  '''
  if not image:
    return None, 'none'
  shape = image_shape(read_header(image))
  if shape:
    values = []
    for box in corner_boxes(*shape):
      try:
        rms = first_value(imstat_dict(imagename=image, box=box).get('rms'))
      except Exception:
        continue
      if rms and rms > 0:
        values.append(rms)
    if len(values) >= 2:
      return median(values), 'corner-boxes'
  mad_sigma = _mad_sigma(image)
  if mad_sigma:
    return mad_sigma, 'mad'
  return None, 'none'


def corner_boxes(nx, ny):
  '''Four imstat box selections ('blcx,blcy,trcx,trcy'), one per corner: squares
  of RMS_CORNER_BOX_FRACTION of the shorter side, inset by RMS_EDGE_MARGIN_FRACTION.
  Empty list when the image is too small to hold them.'''
  short = min(nx, ny)
  side = max(8, int(short * RMS_CORNER_BOX_FRACTION))
  margin = max(2, int(short * RMS_EDGE_MARGIN_FRACTION))
  if side + 2 * margin > short:
    return []
  near_x, far_x = margin, nx - margin - side
  near_y, far_y = margin, ny - margin - side
  return [f"{x},{y},{x + side - 1},{y + side - 1}"
          for x in (near_x, far_x) for y in (near_y, far_y)]


def _mad_sigma(image):
  '''Robust whole-image noise: 1.4826 * the median absolute deviation, which
  imstat reports directly as medabsdevmed.'''
  try:
    mad = first_value(imstat_dict(imagename=image).get('medabsdevmed'))
  except Exception as exc:
    print(f"image_data: imstat failed on {image}: {exc}")
    return None
  return mad * MAD_TO_SIGMA if mad and mad > 0 else None


def imstat_dict(**kwargs) -> dict:
  '''imstat as a plain dict. casatasks is annotated as returning None, so the
  cast lives here instead of at every call site; a genuinely empty result
  becomes {} so .get() is always valid.'''
  return cast(dict, ct.imstat(**kwargs)) or {}


#----------------------------------------------------------- quantity conversion
#Shared with source_fit: CASA hands back numpy scalars, 1-element arrays and
#quantity dicts interchangeably for the same conceptual value.

def first_value(value):
  '''Reduce a numpy scalar / 1-element array / number to a plain float, or None
  if it isn't numeric (dicts and strings included -- see to_arcsec for those).'''
  if value is None or isinstance(value, (str, bytes, dict)):
    return None
  try:
    if hasattr(value, '__len__'):
      return float(value[0]) if len(value) else None
    return float(value)
  except (TypeError, ValueError, IndexError):
    return None


def to_arcsec(quantity):
  '''A CASA quantity dict -> float arcsec, converting units via astropy when
  needed. Plain numbers pass through unconverted (already assumed arcsec); an
  unrecognised unit falls back to the raw value rather than losing it.'''
  if not isinstance(quantity, dict):
    return first_value(quantity)
  value, unit = first_value(quantity.get('value')), quantity.get('unit')
  if value is None or unit in (None, '', 'arcsec'):
    return value
  try:
    return convert_unit(value, u.Unit(unit), ARCSEC)
  except Exception as exc:
    print(f"image_data: could not convert {value} {unit} to arcsec ({exc}); using as-is.")
    return value


def convert_unit(value, from_unit, to_unit) -> float:
  '''value in `from_unit` -> float in `to_unit`, via astropy. Wrapped because
  astropy's operator-built Quantity defeats static type inference (the checker
  sees ndarray, not Quantity), so the cast lives in exactly one place. Shared
  with source_fit, which converts frequencies and angles the same way.'''
  return float(cast(Any, value * from_unit).to(to_unit).value)
