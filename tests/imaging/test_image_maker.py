'''Cleaner's parameter builders, on stand-in options: no MS, no tclean.'''
import tempfile
import unittest
from types import SimpleNamespace

from classes.constants import AUTOMASK_KWARGS, SELF_CAL_NSIGMA
from image_generation.image_maker import Cleaner


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
