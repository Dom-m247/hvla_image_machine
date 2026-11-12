"""Positions on the sky, in J2000 radians: the data's pointing and the angles between them,
and the primary beam they sit in."""
import math

import casatools

from classes.constants import PB_FWHM_ARCMIN_GHZ


def mean_freq_ghz(vis):
  '''Mean frequency of an MS's spws, in GHz.'''
  msmd = casatools.msmetadata()
  msmd.open(vis)
  try:
    freqs = [msmd.meanfreq(spw) for spw in range(msmd.nspw())]
  finally:
    msmd.close()
  return sum(freqs) / len(freqs) / 1e9


def pb_fwhm_arcsec(freq_ghz):
  '''Primary-beam FWHM at a frequency, in arcsec.'''
  return PB_FWHM_ARCMIN_GHZ / freq_ghz * 60


def ms_pointing(vis, field=0):
  '''(ra, dec) of a field's phase centre in an MS, converted to J2000.'''
  msmd = casatools.msmetadata()
  msmd.open(vis)
  try:
    direction = msmd.phasecenter(field)
  finally:
    msmd.close()
  return to_j2000(direction)


def to_j2000(direction):
  '''(ra, dec) in radians of a CASA direction measure, converted to J2000.'''
  if direction.get('refer') != 'J2000':
    me = casatools.measures()
    try:
      direction = me.measure({'type': 'direction', **direction}, 'J2000')
    finally:
      me.done()
  return float(direction['m0']['value']) % (2 * math.pi), float(direction['m1']['value'])


def phasecenter(ra, dec):
  '''A tclean phasecenter string for a J2000 position in radians.'''
  return f"J2000 {ra:.12f}rad {dec:.12f}rad"


def separation(ra1, dec1, ra2, dec2):
  '''Angle between two positions, all in radians.'''
  hav = (math.sin((dec2 - dec1) / 2) ** 2
         + math.cos(dec1) * math.cos(dec2) * math.sin((ra2 - ra1) / 2) ** 2)
  return 2 * math.asin(min(1.0, math.sqrt(hav)))
