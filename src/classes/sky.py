"""Positions on the sky, in J2000 radians: the data's pointing and the angles between them."""
import math

import casatools


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
