'''catalog_client error branches, cache and parsers, in one process with pacing off.'''
import contextlib
import sqlite3

import requests
from API_integrations import catalog_client as cc

from .support import FOUND_3C15, CatalogTestCase, answer, fixture, quiet, raises

LOOKUP = fixture('ned_lookup_3C15')
UNKNOWN = fixture('ned_lookup_unknown')
OTHER_ERROR = UNKNOWN.replace(b'Failed to resolve input object name', b'Database unavailable')
EMPTY = b'''<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE><TABLE name="ConeSearch"><FIELD name="Object Name" datatype="char" arraysize="*"/>
<DATA><TABLEDATA></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>'''
PHOT = b'''<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE><TABLE name="PhotometryOfObject">
<FIELD name="Frequency" datatype="double"/><FIELD name="Freq. Unit" datatype="char" arraysize="*"/>
<FIELD name="Frequency (Hz)" datatype="double" unit="Hz"/><FIELD name="Flux Density" datatype="double" unit="Jy"/>
<DATA><TABLEDATA>
<TR><TD>1.4</TD><TD>GHz</TD><TD>1.4e9</TD><TD>4.1</TD></TR>
<TR><TD>4.15</TD><TD>keV</TD><TD>1.0e18</TD><TD></TD></TR>
<TR><TD>5</TD><TD>GHz</TD><TD>5e9</TD><TD>NaN</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>'''
DAY = 86400

#response -> expected cooldown: blocks pause the whole service ('ned'), outages one endpoint
FAILURES = [
    ('403', answer(403), {'ned': 86400}),
    ('503 Retry-After 120', answer(503, headers={'Retry-After': '120'}), {'ned-lookup': 120}),
    ('503 Retry-After 5 (floor)', answer(503, headers={'Retry-After': '5'}), {'ned-lookup': 60}),
    ('429 no Retry-After', answer(429), {'ned': 600}),
    ('ReadTimeout', raises(requests.ReadTimeout('read timed out')), {'ned-lookup': 300}),
    ('ConnectionError', raises(requests.ConnectionError('refused')), {'ned-lookup': 300}),
    ('500', answer(500), {}),
    ('302', answer(302, headers={'Location': 'elsewhere'}), {})]

def ttl(key):
  with contextlib.closing(sqlite3.connect(cc.CACHE_PATH)) as db:
    row = db.execute('SELECT expires - fetched FROM entries WHERE key = ?', (key,)).fetchone()
  return row and row[0]


class TestFailedRequests(CatalogTestCase):
  def test_each_failure_returns_none_with_its_cooldown(self):
    for label, respond, want in FAILURES:
      with self.subTest(label):
        self.fresh()
        calls = self.serve(respond)
        value, _ = quiet(cc.ned_lookup, '3C 15')
        self.assertIsNone(value)
        self.assertEqual(len(calls), 1)
        self.assertIsNone(cc._cache_get('ned:lookup:3C 15'))
        self.assertCooldowns(want)

  def test_cooldown_stops_later_calls_with_one_message(self):
    calls = self.serve(answer(403))
    quiet(cc.ned_lookup, '3C 15')
    _, out = quiet(lambda: [cc.ned_lookup('3C 15'), cc.ned_lookup('3C 48'), cc.ned_lookup('3C 48')])
    self.assertEqual(len(calls), 1)
    self.assertEqual(out.count('paused until'), 1, out)

  def test_block_on_lookup_pauses_photometry(self):
    calls = self.serve(answer(403))
    quiet(cc.ned_lookup, '3C 15')
    quiet(cc.ned_photometry, '3C 15')
    self.assertEqual(len(calls), 1)

  def test_timeout_on_lookup_leaves_photometry_open(self):
    self.serve(raises(requests.ReadTimeout('read timed out')))
    quiet(cc.ned_lookup, '3C 15')
    calls = self.serve(answer(200, PHOT))
    quiet(cc.ned_photometry, '3C 15')
    self.assertEqual(len(calls), 1)

  def test_server_error_is_not_cached(self):
    calls = self.serve(answer(500))
    quiet(cc.ned_lookup, '3C 15')
    quiet(cc.ned_lookup, '3C 15')
    self.assertEqual(len(calls), 2)


class TestAnswers(CatalogTestCase):
  def test_found_is_cached_90_days(self):
    calls = self.serve(answer(200, LOOKUP))
    first, _ = quiet(cc.ned_lookup, '  3C   15 ')
    second, _ = quiet(cc.ned_lookup, '3C 15')
    self.assertEqual(first, FOUND_3C15)
    self.assertEqual(second, FOUND_3C15)
    self.assertEqual(len(calls), 1, 'second call should be a cache hit')
    self.assertAlmostEqual(ttl('ned:lookup:3C 15'), 90 * DAY, delta=1)

  def test_not_found_is_cached_7_days(self):
    for label, body in [('unknown name (NED QUERY_STATUS)', UNKNOWN), ('zero rows', EMPTY)]:
      with self.subTest(label):
        self.fresh()
        calls = self.serve(answer(200, body))
        self.assertIsNone(quiet(cc.ned_lookup, '3C 999')[0])
        self.assertIsNone(quiet(cc.ned_lookup, '3C 999')[0])
        self.assertEqual(len(calls), 1, 'second call should be a cache hit')
        self.assertEqual(cc._cache_get('ned:lookup:3C 999'), {})
        self.assertAlmostEqual(ttl('ned:lookup:3C 999'), 7 * DAY, delta=1)

  def test_other_query_error_raises_and_caches_nothing(self):
    self.serve(answer(200, OTHER_ERROR))
    with self.assertRaisesRegex(ValueError, 'Database unavailable'):
      quiet(cc.ned_lookup, '3C 15')
    self.assertIsNone(cc._cache_get('ned:lookup:3C 15'))

  def test_photometry_drops_masked_and_nan_and_is_cached_30_days(self):
    self.serve(answer(200, PHOT))
    rows, _ = quiet(cc.ned_photometry, '3C 15')
    self.assertEqual(rows, [[1.4e9, 4.1]])
    self.assertAlmostEqual(ttl('ned:phot:3C 15'), 30 * DAY, delta=1)


class TestClearCache(CatalogTestCase):
  def setUp(self):
    super().setUp()
    self.serve(answer(200, LOOKUP))
    quiet(cc.ned_lookup, '3C 15')
    self.serve(answer(200, UNKNOWN))
    quiet(cc.ned_lookup, '3C 999')       #cached {}
    quiet(cc.ned_photometry, '3C 999')   #cached []

  def test_not_found_only_keeps_resolved_names(self):
    self.assertEqual(cc.clear_cache(not_found_only=True), 2)
    self.assertIsNone(cc._cache_get('ned:lookup:3C 999'))
    self.assertIsNone(cc._cache_get('ned:phot:3C 999'))
    self.assertEqual(cc._cache_get('ned:lookup:3C 15'), FOUND_3C15)

  def test_everything(self):
    self.assertEqual(cc.clear_cache(), 3)
    self.assertIsNone(cc._cache_get('ned:lookup:3C 15'))


class TestRequests(CatalogTestCase):
  def test_empty_name_sends_nothing(self):
    calls = self.serve(answer(200, LOOKUP))
    self.assertIsNone(cc.ned_lookup('   '))
    self.assertIsNone(cc.ned_photometry(''))
    self.assertEqual(calls, [])

  def test_user_agent_names_the_project(self):
    self.assertRegex(cc._session.headers['User-Agent'], r'^hvla_image_machine/')
