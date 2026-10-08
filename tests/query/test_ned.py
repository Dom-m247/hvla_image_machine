'''NED.py end to end on NED responses captured 2026-10-06, served by a fake session.'''
import unittest
from urllib.parse import parse_qs

from API_integrations import catalog_client as cc
from API_integrations.NED import NED_API
from classes.constants import BAND_MHZ_RANGES, MIN_FLUX_FOR_SELF_CAL

from .support import FOUND_3C15, CatalogTestCase, FakeResp, fixture, quiet

SERVED = {('ConeSearchByTarget', '3C 15'): 'ned_lookup_3C15', ('ConeSearchByTarget', '3C 999'): 'ned_lookup_unknown',
          ('ConeSearchByTarget', '3C 58'): 'ned_lookup_3C58', ('PhotometryOfObject', '3C 15'): 'ned_photometry_3C15'}

def respond(method, url, kw):
  service, target = url.rsplit('/', 1)[1], parse_qs(kw['params'])['TARGET'][0]
  return FakeResp(200, fixture(SERVED[service, target]))


class TestNedParsers(unittest.TestCase):
  def test_lookup(self):
    self.assertEqual(cc._parse_lookup(fixture('ned_lookup_3C15')), FOUND_3C15)

  def test_lookup_unknown_name_is_not_found(self):
    self.assertEqual(cc._parse_lookup(fixture('ned_lookup_unknown')), {})

  def test_lookup_without_redshift(self):
    found = cc._parse_lookup(fixture('ned_lookup_3C58'))
    self.assertIsNone(found['redshift'])
    self.assertEqual(found['name'], '3C 058')

  def test_photometry_drops_masked_rows(self):
    self.assertEqual(len(cc._parse_photometry(fixture('ned_photometry_3C15'))), 164 - 2)

  def test_photometry_for_unknown_name_is_empty(self):
    self.assertEqual(cc._parse_photometry(fixture('ned_lookup_unknown')), [])


class TestNedApi(CatalogTestCase):
  def setUp(self):
    super().setUp()
    self.calls = self.serve(respond)

  def test_obj_exists(self):
    got, _ = quiet(NED_API.obj_exists, '3C 15')
    self.assertEqual(got, {'ra_decl': {'ra': 9.2671047, 'decl': -1.1522973}, 'alias': '3C 015',
                           'redshift': 0.07367822})

  def test_obj_exists_unknown_name_is_false(self):
    self.assertIs(quiet(NED_API.obj_exists, '3C 999')[0], False)

  def test_obj_exists_without_redshift_gives_empty_string(self):
    got, _ = quiet(NED_API.obj_exists, '3C 58')
    self.assertEqual(got['redshift'], '')
    self.assertEqual(got['alias'], '3C 058')

  def test_self_cal_potential_agrees_with_in_band_rows(self):
    low, high = (f * 1e6 for f in BAND_MHZ_RANGES['L'])
    rows = cc._parse_photometry(fixture('ned_photometry_3C15'))
    want = any(flux >= MIN_FLUX_FOR_SELF_CAL for freq, flux in rows if low <= freq <= high)
    self.assertIs(quiet(NED_API.check_self_cal_potential, '3C 15', 'L')[0], want)

  def test_repeat_calls_are_cache_hits(self):
    lookups = [(NED_API.obj_exists, '3C 15'), (NED_API.check_self_cal_potential, '3C 15', 'L'),
               (NED_API.obj_exists, '3C 999')]
    for fn, *args in lookups:
      quiet(fn, *args)
    sent = len(self.calls)
    for fn, *args in lookups:
      quiet(fn, *args)
    self.assertEqual(len(self.calls), sent)
