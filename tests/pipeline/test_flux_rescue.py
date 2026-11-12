'''The catalogue flux-scale rescue on a synthetic observation: no MS, no CASA task.'''
import unittest
from types import SimpleNamespace

from classes.constants import FLUX_SCALE_CATALOGUE, FLUX_SCALE_MANUAL, FLUX_SCALE_STANDARD
from classes.observations_class import Obs_data
from classes.source_class import flux_scale, flux_scale_record, source_info
from data_calibration.cal_split import define_split_fields_phase_cal

FIELDS = [  #(name, ra, decl), J2000
  ('NGC4579', '12:37:43.52', '+11.49.05.5'),
  ('1308+326', '13:10:28.66', '+32.20.43.8'),
  ('1236+077', '12:39:24.59', '+07.30.17.2'),
  ('1642+690', '16:42:07.85', '+68.56.39.8'),
]


def observation(c_config=True):
  '''Two antennas 3 km apart (C configuration) or 30 km apart (A), every field in spws 0,1.'''
  span = 3000.0 if c_config else 30000.0
  antennas = [{'id': i, 'name': f'VA0{i}', 'station': 'W1', 'diameter': '25.0', 'longitude': '',
               'latitude': '', 'east_offset': x, 'north_offset': 0.0, 'elevation': 0.0,
               'x': None, 'y': None, 'z': None} for i, x in enumerate((0.0, span))]
  fields = [{'id': i, 'code': None, 'name': n, 'ra': ra, 'decl': dec, 'epoch': 'J2000',
             'src_id': i, 'nrows': 100} for i, (n, ra, dec) in enumerate(FIELDS)]
  scans = [{'date': '01-Jan-1990', 'timerange_start': '', 'timerange_end': '', 'scan': i,
            'field_id': i, 'field_name': n, 'nrows': 100, 'spw_ids': '[0,1]',
            'average_intervals': ''} for i, (n, _, _) in enumerate(FIELDS)]
  return Obs_data(antennas=antennas, fields=fields, observations=scans)


def options(band, c_config=True):
  return SimpleNamespace(observation_data=observation(c_config), band=band, array_config='',
                         spw_selection='0,1', search_alias='', flux_cal_manual=None,
                         source_ids=SimpleNamespace(field_id=0))


class Rescue(unittest.TestCase):
  def candidates(self, band, c_config=True):
    return source_info(options(band), type='')._catalogue_flux_cals(options(band, c_config))

  def test_nearest_listed_calibrator_first_with_its_catalogue_flux(self):
    found = self.candidates('C')
    self.assertEqual([str(f['field'].name) for f in found], ['1236+077', '1308+326', '1642+690'])
    self.assertEqual(found[0]['flux'], {'flux': 0.7, 'reffreq': '4.997GHz',
                                        'origin': FLUX_SCALE_CATALOGUE})

  def test_a_calibrator_rated_x_in_this_configuration_is_skipped(self):
    names = [str(f['field'].name) for f in self.candidates('L')]
    self.assertNotIn('1642+690', names)   #L band: X in A, B and C, S in D
    self.assertEqual(names, ['1236+077', '1308+326'])
    a_config = [str(f['field'].name) for f in self.candidates('L', c_config=False)]
    self.assertEqual(a_config, ['1236+077', '1308+326'])

  def test_ku_band_uses_the_lists_u_code(self):
    self.assertTrue(self.candidates('Ku'))


class Origin(unittest.TestCase):
  def test_origin_follows_the_manual_flux(self):
    self.assertEqual(flux_scale(SimpleNamespace(flux_cal_manual=None)), FLUX_SCALE_STANDARD)
    self.assertEqual(flux_scale(SimpleNamespace(flux_cal_manual={'flux': 1.0, 'reffreq': ''})),
                     FLUX_SCALE_MANUAL)
    record = flux_scale_record(SimpleNamespace(
      flux_cal_name='1236+077',
      flux_cal_manual={'flux': 0.7, 'reffreq': '4.997GHz', 'origin': FLUX_SCALE_CATALOGUE}))
    self.assertEqual(record, {'origin': FLUX_SCALE_CATALOGUE, 'calibrator': '1236+077',
                              'flux_jy': 0.7, 'reffreq': '4.997GHz'})


class SharedCalibrator(unittest.TestCase):
  def test_the_split_lists_a_shared_calibrator_once(self):
    opts = SimpleNamespace(target_is_phase_cal=False, source_ids=SimpleNamespace(field_id=0),
                           flux_cal=SimpleNamespace(field_id=2), phase_cal=SimpleNamespace(field_id=2))
    self.assertEqual(define_split_fields_phase_cal(opts), '0,2')


if __name__ == '__main__':
  unittest.main()
