'''The target's measurement on synthetic J2000 images: a detection, an upper limit, and a
target that lies on its own field rather than the main image.'''
import math
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import casatools
import numpy as np

from image_generation import source_fit

CELL = 1.0     #arcsec
BEAM = 4.0     #arcsec FWHM
CENTRE = (150.0, 30.0)   #degrees, at pixel (32, 32)


def make_field(base, size=64, centre=CENTRE, sources=(), pb=1.0, noise=0.001, seed=1):
  '''<base>.image.tt0 (noise plus point sources (x, y, peak Jy/beam)) and a flat
  <base>.pb.tt0 of `pb`.'''
  rng = np.random.default_rng(seed)
  pixels = rng.normal(0, noise, (size, size))
  x, y = np.indices((size, size))
  sigma = BEAM / CELL / (2 * math.sqrt(2 * math.log(2)))
  for sx, sy, peak in sources:
    pixels += peak * np.exp(-((x - sx) ** 2 + (y - sy) ** 2) / (2 * sigma ** 2))
  cs = casatools.coordsys()
  cs.newcoordsys(direction=True, spectral=True, stokes=['I'])   #axes: ra, dec, stokes, freq
  cs.setreferencecode('J2000', 'direction')
  cs.setunits(['rad', 'rad', '', 'Hz'])
  cs.setreferencepixel([size // 2, size // 2, 0, 0])
  cs.setreferencevalue([math.radians(centre[0]), math.radians(centre[1]), 1, 1.4e9])
  cs.setincrement([-math.radians(CELL / 3600), math.radians(CELL / 3600), 1, 1e6])
  for suffix, data in (('.image.tt0', pixels), ('.pb.tt0', np.full((size, size), pb))):
    ia = casatools.image()
    ia.fromarray(outfile=base + suffix, pixels=data.reshape(size, size, 1, 1),
                 csys=cs.torecord(), overwrite=True)
    if suffix == '.image.tt0':
      ia.setrestoringbeam(major=f'{BEAM}arcsec', minor=f'{BEAM}arcsec', pa='0deg')
      ia.setbrightnessunit('Jy/beam')
    ia.close()
  cs.done()


def offset(dx_px, dy_px, centre=CENTRE):
  '''The sky position dx, dy pixels from a field's centre pixel, in degrees.'''
  dec = centre[1] + dy_px * CELL / 3600
  return centre[0] - dx_px * CELL / 3600 / math.cos(math.radians(centre[1])), dec


def options(base, position, sigma=5.0):
  return SimpleNamespace(source_ra=position[0], source_decl=position[1], best_image_base=base,
                         detection_sigma=sigma, pointing=tuple(math.radians(c) for c in CENTRE),
                         sysArgs=SimpleNamespace(importRun=True), rms_region='',
                         flux_cal_manual=None, flux_cal_name='3C286', results_dir='', results_name='')


class MeasureTarget(unittest.TestCase):
  def setUp(self):
    tmp = tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    self.dir = Path(tmp.name)
    cwd = os.getcwd()
    os.chdir(self.dir)
    self.addCleanup(os.chdir, cwd)

  def measure(self, opts, base):
    from classes.image_data import Image, imstat_dict
    image = Image(opts, imstat_dict(imagename=base + '.image.tt0'), base=base)
    return source_fit.fit_best_image(opts, image)

  def test_a_source_at_the_target_is_detected_and_fitted_there(self):
    make_field('main', sources=[(40, 30, 0.05), (14, 50, 0.5)])   #the brighter one must not win
    record = self.measure(options('main', offset(8, -2)), 'main')
    self.assertTrue(record['detected'])
    self.assertGreater(record['snr'], 20)
    self.assertEqual(record['image_field'], 'main')
    self.assertEqual(record['target']['position_from'], 'NED')
    self.assertAlmostEqual(record['peak_flux']['value'], 0.05, delta=0.005)
    self.assertAlmostEqual(record['position']['ra_deg'], offset(8, -2)[0], places=4)
    self.assertIsNone(record['upper_limit_jy'])
    self.assertAlmostEqual(record['pointing_offset_arcmin'], math.hypot(8, 2) / 60, places=3)

  def test_no_source_is_an_upper_limit_corrected_for_the_beam(self):
    make_field('quiet', pb=0.5)
    record = self.measure(options('quiet', offset(0, 0)), 'quiet')
    self.assertFalse(record['detected'])
    self.assertAlmostEqual(record['pb_response'], 0.5)
    self.assertAlmostEqual(record['upper_limit_jy'],
                           5 * record['rms_jy_per_beam'] / 0.5)

  def test_a_target_off_the_main_image_is_measured_on_its_field(self):
    make_field('run')
    field_centre = offset(200, 0)
    make_field('run_targetfield', centre=field_centre, sources=[(32, 32, 0.03)], pb=0.25)
    record = self.measure(options('run', field_centre), 'run')
    self.assertEqual(record['image_field'], 'targetfield')
    self.assertTrue(record['detected'])
    self.assertAlmostEqual(record['pb_response'], 0.25)

  def test_a_target_on_no_field_is_noted(self):
    make_field('lone')
    record = self.measure(options('lone', offset(500, 0)), 'lone')
    self.assertIsNone(record['detected'])
    self.assertIn('outside', record['note'])


if __name__ == '__main__':
  unittest.main()
