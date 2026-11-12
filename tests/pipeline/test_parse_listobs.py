'''parse_listobs on listobs text with field names that hold spaces, blank and set Code
columns, and the epoch/SrcId run-together listobs writes for B1950_VLA fields.'''
import unittest

from data_calibration import parse_listobs as pl
from classes.observations_class import casa_field

LISTOBS = '''\
           MeasurementSet Name:  /x/measurement_sets/VB0081_fullset.ms      MS Version 2
   Observer: unavailable     Project: VB74G
Observation: VLA
Data records: 208000       Total elapsed time = 34290 seconds
   Observed from   26-Sep-1987/13:38:10.0   to   26-Sep-1987/23:09:40.0 (TAI)

   ObservationID = 0         ArrayID = 0
  Date        Timerange (TAI)          Scan  FldId FieldName             nRows     SpwIds   Average Interval(s)    ScanIntent
  26-Sep-1987/13:38:10.0 - 13:41:50.0     3      0 3C274                    14300  [0,1]  [10, 10]
              14:12:50.0 - 14:15:30.0     8      1 NGC 4565_1               10400  [0,1]  [10, 10]
              14:52:50.0 - 14:55:30.0    12      2 A 2218 1                 10400  [0,1]  [3.33, 3.33]
           (nRows = Total number of rows per scan)
Fields: 3
  ID   Code Name                RA               Decl           Epoch   SrcId      nRows
  0         3C274               12:28:17.569000 +12.40.01.99000 B1950_VLA0         14300
  1    A    NGC 4565_1          12:36:20.780000 +25.59.15.60000 J2000   1          10400
  2         A 2218 1            16:35:54.000000 +66.13.00.00000 J2000   2          10400
Spectral Windows:  (2 unique spectral windows and 1 unique polarization setups)
  SpwID  Name                                #Chans   Frame   Ch0(MHz)  ChanWid(kHz)  TotBW(kHz) CtrFreq(MHz)  Corrs
  0      none                                     1   TOPO    4885.100     50000.000     50000.0   4885.1000   RR  RL  LR  LL
  1      none                                     1   TOPO    4835.100     50000.000     50000.0   4835.1000   RR  RL  LR  LL
Sources: 3
  ID   Name                SpwId RestFreq(MHz)  SysVel(km/s)
  0    3C274               any   0              0
  1    NGC 4565_1          any   0              0
  2    A 2218 1            any   0              0
Antennas: 2:
  ID   Name  Station   Diam.    Long.         Lat.                Offset from array center (m)                ITRF Geocentric coordinates (m)
                                                                     East         North     Elevation               x               y               z
  0    VA01  W36       25.0 m   -107.37.05.0  +33.53.02.1     -1248.6281     -1105.9301      -62.7616 -1600592.843000 -5035415.389000  3539212.120000
  1    VA02  E32       25.0 m   -107.37.05.0  +33.53.02.1      4400.6281      -300.9301      -12.7616 -1600592.843000 -5035415.389000  3539212.120000
'''


class Fields(unittest.TestCase):
  def test_names_with_spaces_and_codes(self):
    fields = pl.parse_fields(LISTOBS)
    self.assertEqual([f['name'] for f in fields], ['3C274', 'NGC 4565_1', 'A 2218 1'])
    self.assertEqual([f['code'] for f in fields], [None, 'A', None])
    self.assertEqual([f['ra'] for f in fields][1], '12:36:20.780000')
    self.assertEqual(fields[2]['decl'], '+66.13.00.00000')

  def test_epoch_run_into_srcid_keeps_nrows(self):
    first = pl.parse_fields(LISTOBS)[0]
    self.assertEqual(first['epoch'], 'B1950_VLA0')
    self.assertIsNone(first['src_id'])
    self.assertEqual(first['nrows'], 14300)
    second = pl.parse_fields(LISTOBS)[1]
    self.assertEqual((second['epoch'], second['src_id'], second['nrows']), ('J2000', 1, 10400))

  def test_without_a_header_a_lone_capital_is_the_code(self):
    text = LISTOBS.replace('  ID   Code Name                RA               Decl           Epoch   SrcId      nRows\n', '')
    fields = pl.parse_fields(text)
    self.assertEqual([(f['code'], f['name']) for f in fields],
                     [(None, '3C274'), ('A', 'NGC 4565_1'), ('A', '2218 1')])


class Scans(unittest.TestCase):
  def test_field_names_with_spaces(self):
    scans = pl.parse_observations(LISTOBS)
    self.assertEqual([s['field_name'] for s in scans], ['3C274', 'NGC 4565_1', 'A 2218 1'])
    self.assertEqual([s['nrows'] for s in scans], [14300, 10400, 10400])
    self.assertEqual(scans[2]['average_intervals'], '[3.33, 3.33]')
    self.assertEqual(scans[1]['date'], '26-Sep-1987')


class Sources(unittest.TestCase):
  def test_names_with_spaces(self):
    sources = pl.parse_sources(LISTOBS)
    self.assertEqual([s['name'] for s in sources], ['3C274', 'NGC 4565_1', 'A 2218 1'])
    self.assertEqual(sources[1]['SpwId'], 'any')


class WholeTable(unittest.TestCase):
  def test_populate_links_fields_to_sources(self):
    data = pl.parseListObs.populate_Obs_data(LISTOBS)
    self.assertEqual([f.src_id for f in data.fields], [0, 1, 2])
    self.assertEqual(data.obs_info.data_records, 208000)
    self.assertEqual(len(data.antennas), 2)


class FieldSelection(unittest.TestCase):
  def test_quoting(self):
    self.assertEqual(casa_field('3C274'), '3C274')
    self.assertEqual(casa_field('02093547'), '"02093547"')
    self.assertEqual(casa_field('NGC 4565_1'), '"NGC 4565_1"')
    self.assertEqual(casa_field('B0206+35'), 'B0206+35')
    self.assertEqual(casa_field(''), '')


if __name__ == '__main__':
  unittest.main()
