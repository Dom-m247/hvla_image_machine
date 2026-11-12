'''outlier_fields' pixel geometry, outlier-file writer and cleanup globs, on synthetic
arrays: no MS, no tclean.'''
import tempfile
import unittest
from fnmatch import fnmatch
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from image_generation import outlier_fields as of


def model_with(*sources, size=64):
  '''A clean-component image with (x, y, flux) components.'''
  model = np.zeros((size, size))
  for x, y, flux in sources:
    model[x, y] += flux
  return model


class Islands(unittest.TestCase):
  def test_separate_sources_are_separate_islands(self):
    islands = of._islands(model_with((10, 10, 0.2), (11, 10, 0.2), (50, 40, 0.1)), merge_px=2)
    self.assertEqual(len(islands), 2)
    bright = max(islands, key=lambda i: i['flux'])
    self.assertAlmostEqual(bright['flux'], 0.4)
    self.assertAlmostEqual(bright['x'], 10.5)
    self.assertEqual(bright['box'], (10.0, 11.0, 10.0, 10.0))

  def test_components_within_merge_radius_join(self):
    self.assertEqual(len(of._islands(model_with((10, 10, 1), (14, 10, 1)), merge_px=2)), 1)
    self.assertEqual(len(of._islands(model_with((10, 10, 1), (16, 10, 1)), merge_px=2)), 2)

  def test_negative_components_and_empty_models(self):
    self.assertEqual(of._islands(model_with((10, 10, -0.5)), merge_px=2), [])
    self.assertEqual(of._islands(np.zeros((8, 8)), merge_px=2), [])


class Boxes(unittest.TestCase):
  def test_square_covers_the_box_and_honours_the_minimum(self):
    self.assertEqual(of._square((0, 10, 0, 4)), (0, 10, -3, 7))
    self.assertEqual(of._square((4, 6, 4, 6), min_half=5), (0, 10, 0, 10))

  def test_overlap_is_strict(self):
    self.assertTrue(of._overlaps((0, 10, 0, 10), (9, 20, 9, 20)))
    self.assertFalse(of._overlaps((0, 10, 0, 10), (10, 20, 0, 10)))
    self.assertFalse(of._overlaps((0, 10, 0, 10), (0, 10, 11, 20)))

  def test_a_square_under_the_gap_clears_the_box(self):
    main = (-10, 10, -10, 10)
    self.assertLessEqual(of._gap((0, 5), main), 0)
    gap = of._gap((25, 3), main)
    self.assertEqual(gap, 15)
    self.assertFalse(of._overlaps(of._box_around((25, 3), gap - 1, gap - 1), main))
    self.assertTrue(of._overlaps(of._box_around((25, 3), gap + 1, gap + 1), main))

  def test_merge_is_transitive_and_keeps_the_target(self):
    entries = [{'box': (0, 10, 0, 10), 'flux': 1.0, 'target': False, 'at': (5, 5)},
               {'box': (8, 18, 0, 10), 'flux': 2.0, 'target': True, 'at': (13, 5)},
               {'box': (17, 27, 0, 10), 'flux': 3.0, 'target': False, 'at': (22, 5)},
               {'box': (100, 110, 100, 110), 'flux': 4.0, 'target': False, 'at': (105, 105)}]
    merged = of._merge(entries)
    self.assertEqual(len(merged), 2)
    joined = next(e for e in merged if e['flux'] == 6.0)
    self.assertTrue(joined['target'])
    self.assertEqual(joined['at'], (13, 5))
    self.assertEqual((joined['box'][0], joined['box'][1]), (0, 27))
    for i, a in enumerate(merged):
      for b in merged[i + 1:]:
        self.assertFalse(of._overlaps(a['box'], b['box']))

  def test_merged_sources_centre_on_their_flux(self):
    merged = of._merge([{'box': (0, 10, 0, 10), 'flux': 1.0, 'target': False, 'at': (0, 0)},
                        {'box': (5, 15, 0, 10), 'flux': 3.0, 'target': False, 'at': (8, 4)}])
    self.assertEqual(merged[0]['at'], (6.0, 3.0))


def radial_pb(size=64, radius=20.0):
  '''A beam falling linearly from 1 at the centre (32, 32) to 0 at radius pixels.'''
  x, y = np.indices((size, size))
  return np.clip(1 - np.hypot(x - size // 2, y - size // 2) / radius, 0, None)


def island(x, y, flux):
  return {'x': float(x), 'y': float(y), 'flux': flux, 'box': (x - 1.0, x + 1.0, y - 1.0, y + 1.0)}


class BeamLimit(unittest.TestCase):
  '''tclean fails outright on a field with no pixel above |pblimit| (seen on M87 data with
  an injected source at 9.6'), so a field's source must sit above it.'''

  def test_beam_at_reads_the_lowest_neighbour(self):
    pb = radial_pb()
    self.assertGreater(of._beam_at(pb, (32, 32)), 0.9)
    self.assertGreater(pb[51, 32], of.PB_LIMIT)       #r = 19: its own pixel is inside...
    self.assertEqual(of._beam_at(pb, (51, 32)), 0.0)  #...but (52, 32) is not
    self.assertEqual(of._beam_at(pb, (32, 57)), 0.0)
    self.assertEqual(of._beam_at(pb, (-4, 10)), 0.0)
    self.assertEqual(of._beam_at(pb, (70, 10)), 0.0)

  def test_beam_edge_is_the_farthest_pixel_above_the_limit(self):
    self.assertAlmostEqual(of._beam_edge(radial_pb(), (32, 32), 0.01), 19.8, places=1)
    self.assertEqual(of._beam_edge(radial_pb(), (32, 32), 2.0), 0.0)

  def test_only_sources_inside_the_beam_get_fields(self):
    inside, past_edge = island(45, 32, 0.1), island(32, 55, 0.1)
    in_main, faint = island(33, 32, 0.1), island(20, 20, 0.001)
    entries, beyond = of._entries([inside, past_edge, in_main, faint], radial_pb(),
                                  of._box_around((32, 32), 5, 5), floor=0.005, margin=2,
                                  min_half=3)
    self.assertEqual([e['at'] for e in entries], [(45.0, 32.0)])
    self.assertEqual(beyond, [past_edge])


class OutlierFile(unittest.TestCase):
  FIELD = {'label': 'outlier01', 'suffix': '_outlier01', 'frame': 'B1950_VLA',
           'ra_rad': -3.0179, 'dec_rad': 0.2213, 'imsize': 144}

  def test_no_fields_no_file(self):
    self.assertEqual(of.tclean_kwargs(SimpleNamespace(), 'x'), {})
    self.assertEqual(of.tclean_kwargs(SimpleNamespace(outlier_fields=[]), 'x'), {})

  def test_each_field_gets_its_own_name_centre_and_mask(self):
    with tempfile.TemporaryDirectory() as tmp:
      base = str(Path(tmp) / 'run_2')
      kw = of.tclean_kwargs(SimpleNamespace(outlier_fields=[self.FIELD]), base)
      lines = Path(kw['outlierfile']).read_text().splitlines()
    self.assertEqual(kw['outlierfile'], base + '.outliers.txt')
    self.assertEqual(lines, [f"imagename={base}_outlier01", 'imsize=[144,144]',
                             'phasecenter=B1950_VLA -3.017900000000rad 0.221300000000rad',
                             'usemask=user', 'mask=box[[0pix,0pix],[143pix,143pix]]'])
    #CASA splits each line on '=': a second one is a parse error
    self.assertTrue(all(line.count('=') == 1 for line in lines))

  def test_a_restart_reuses_the_fields_mask(self):
    with tempfile.TemporaryDirectory() as tmp:
      base = str(Path(tmp) / 'run_2')
      Path(base + '_outlier01.mask').mkdir()
      kw = of.tclean_kwargs(SimpleNamespace(outlier_fields=[self.FIELD]), base)
      lines = Path(kw['outlierfile']).read_text().splitlines()
    self.assertEqual(lines[-1], 'mask=')

  def test_globs_catch_this_cleans_fields_only(self):
    patterns = of.product_globs('ms/run')
    def caught(path):
      return any(fnmatch(path, p) for p in patterns)
    self.assertTrue(caught('ms/run_outlier01.image.tt0'))
    self.assertTrue(caught('ms/run_targetfield.pbcorimage'))
    self.assertFalse(caught('ms/run_0_outlier01.image.tt0'))  #another cycle's
    self.assertFalse(caught('ms/run_pbsweep.model'))          #the search image
    self.assertFalse(caught('ms/run.image.tt0'))


if __name__ == '__main__':
  unittest.main()
