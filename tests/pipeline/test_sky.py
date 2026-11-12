'''classes.sky's conversions, against positions worked out by hand.'''
import math
import unittest

from classes import sky

ARCSEC = math.pi / 180 / 3600


class Sky(unittest.TestCase):
  def test_b1950_vla_pointing_reaches_m87_in_j2000(self):
    #3C274's phase centre in VB0081 (B1950_VLA), against M87 at 12:30:49.4233 +12:23:28.043
    direction = {'m0': {'unit': 'rad', 'value': 3.2650433549639084},
                 'm1': {'unit': 'rad', 'value': 0.22108468637820247}, 'refer': 'B1950_VLA'}
    ra, dec = sky.to_j2000(direction)
    m87 = (math.radians(187.7059304), math.radians(12.3911231))
    self.assertLess(sky.separation(ra, dec, *m87) / ARCSEC, 1.0)

  def test_j2000_passes_through_with_ra_wrapped(self):
    j2000 = {'m0': {'unit': 'rad', 'value': -3.0}, 'm1': {'unit': 'rad', 'value': 0.2},
             'refer': 'J2000'}
    self.assertAlmostEqual(sky.to_j2000(j2000)[0], 2 * math.pi - 3.0)

  def test_separation(self):
    self.assertAlmostEqual(sky.separation(1.0, 0.2, 1.0, 0.2 + 60 * ARCSEC) / ARCSEC, 60, places=6)
    self.assertAlmostEqual(sky.separation(0.0, 0.0, 2 * math.pi - 30 * ARCSEC, 0.0) / ARCSEC,
                           30, places=4)

  def test_phasecenter_string(self):
    self.assertEqual(sky.phasecenter(3.25, -0.5), 'J2000 3.250000000000rad -0.500000000000rad')


if __name__ == '__main__':
  unittest.main()
