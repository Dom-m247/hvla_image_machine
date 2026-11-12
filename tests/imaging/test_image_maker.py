'''Cleaner's parameter builders, on stand-in options: no MS, no tclean.'''
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from classes import sky
from classes.constants import AUTOMASK_KWARGS, SELF_CAL_NSIGMA
from image_generation.image_maker import Cleaner


def imaging_options(band, config, fov='primary_beam', custom_cell=''):
  return SimpleNamespace(field_of_view=fov, band=band, array_config=config,
                         use_custom_cell_size=bool(custom_cell), cell_size=custom_cell,
                         image_size=[256, 256], calibrated_filename='x',
                         observation_data=SimpleNamespace(antennas=[]),
                         decision=lambda name: 'off')


class SizeImage(unittest.TestCase):
  def size(self, options, freq_ghz):
    with mock.patch.object(sky, 'mean_freq_ghz', return_value=freq_ghz), \
         mock.patch('classes.run_log.note'):
      Cleaner.size_image(options)
    return options.cell_size, options.image_size

  def test_primary_beam_field_is_1024_px_at_a_fifth_of_a_beam(self):
    self.assertEqual(self.size(imaging_options('C', 'A'), 4.86), ('0.066arcsec', [1024, 1024]))

  def test_never_wider_than_twice_the_beam_fwhm(self):
    cell, size = self.size(imaging_options('X', 'D'), 8.4)
    self.assertEqual(cell, '1.44arcsec')
    fwhm = 43.0 / 8.4 * 60
    self.assertLessEqual(size[0] * 1.44, 2 * fwhm)
    self.assertGreater(size[0] * 1.44, 1.8 * fwhm)

  def test_a_custom_cell_is_kept(self):
    self.assertEqual(self.size(imaging_options('C', 'A', custom_cell='0.1arcsec'), 4.86),
                     ('0.1arcsec', [1024, 1024]))

  def test_fixed_keeps_the_image_size_and_a_tenth_of_a_beam(self):
    self.assertEqual(self.size(imaging_options('C', 'A', fov='fixed'), 4.86),
                     ('0.033arcsec', [256, 256]))

  def test_outlier_fields_follow_the_field_of_view(self):
    self.assertTrue(Cleaner.wants_outlier_fields(imaging_options('C', 'A')))
    self.assertFalse(Cleaner.wants_outlier_fields(imaging_options('C', 'A', fov='fixed')))


class Gridder(unittest.TestCase):
  def test_curvature_criterion(self):
    self.assertTrue(sky.needs_wprojection(15 * 60, 36000, 1.4))    #L band A: half the beam
    self.assertFalse(sky.needs_wprojection(2 * 60, 36000, 1.4))    #...but not a 4' field
    self.assertFalse(sky.needs_wprojection(5 * 60, 1000, 4.86))    #C band D

  def choose(self, side, cell, span_m, freq_ghz, fields=()):
    antennas = [SimpleNamespace(east_offset=0.0, north_offset=0.0),
                SimpleNamespace(east_offset=span_m, north_offset=0.0)]
    options = SimpleNamespace(cell_size=f"{cell}arcsec", image_size=[side, side],
                              outlier_fields=list(fields), calibrated_filename='x',
                              observation_data=SimpleNamespace(antennas=antennas))
    with mock.patch.object(sky, 'mean_freq_ghz', return_value=freq_ghz), \
         mock.patch('classes.run_log.note'):
      Cleaner.choose_gridder(options)
    return options.gridder

  def test_wide_low_frequency_images_are_w_projected(self):
    self.assertEqual(self.choose(4096, 1.12, 36000, 0.33), 'wproject')      #P band A, 76'
    self.assertEqual(self.choose(1024, 0.26, 36000, 1.4), 'standard')       #L band A, 4.4'
    self.assertEqual(self.choose(1024, 0.26, 36000, 1.4, [{'imsize': 1024}]), 'standard')

  def test_kwargs(self):
    self.assertEqual(Cleaner._gridder_kwargs('wproject'), {'gridder': 'wproject', 'wprojplanes': -1})
    self.assertEqual(Cleaner._gridder_kwargs('standard'), {'gridder': 'standard'})


def write_image(path, value_at):
  '''A 16x16 CASA image, zero but for {(x, y): value}.'''
  import casatools
  import numpy as np
  pixels = np.zeros((16, 16, 1, 1))
  for (x, y), value in value_at.items():
    pixels[x, y, 0, 0] = value
  ia = casatools.image()
  ia.fromarray(outfile=path, pixels=pixels, overwrite=True)
  ia.close()


class CleanedFlux(unittest.TestCase):
  def test_main_and_outlier_models_add_up(self):
    with tempfile.TemporaryDirectory() as tmp:
      base = f"{tmp}/run"
      write_image(base + '.model.tt0', {(3, 3): 0.010, (8, 8): 0.004})
      write_image(base + '_outlier01.model.tt0', {(5, 5): 0.012})
      options = SimpleNamespace(outlier_fields=[{'suffix': '_outlier01'}, {'suffix': '_outlier02'}])
      self.assertAlmostEqual(Cleaner.cleaned_flux(options, base), 0.026)
      self.assertAlmostEqual(Cleaner.cleaned_flux(SimpleNamespace(), base), 0.014)


class MaskKwargs(unittest.TestCase):
  def test_automatic_imaging_uses_the_vla_automask(self):
    kw = Cleaner._mask_kwargs(SimpleNamespace(mask='', interactive_image=False))
    self.assertEqual(kw, {'nsigma': SELF_CAL_NSIGMA, 'usemask': 'auto-multithresh',
                          **AUTOMASK_KWARGS})
    self.assertEqual(kw['minbeamfrac'], 0.1)

  def test_a_saved_mask_or_a_person_needs_no_automask(self):
    with tempfile.TemporaryDirectory() as mask:
      kw = Cleaner._mask_kwargs(SimpleNamespace(mask=mask, interactive_image=False))
    self.assertEqual(kw['usemask'], 'user')
    self.assertNotIn('sidelobethreshold', kw)
    kw = Cleaner._mask_kwargs(SimpleNamespace(mask='', interactive_image=True), nsigma=4)
    self.assertEqual(kw, {'nsigma': 4})


if __name__ == '__main__':
  unittest.main()
