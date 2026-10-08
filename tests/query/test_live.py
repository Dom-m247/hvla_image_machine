'''The queries behind the fixtures, sent to NED and SIMBAD for real, to find which ones a service
change has broken. Skipped unless HVLA_LIVE_API=1; then 7 requests at most, through the shared gate.
HVLA_LIVE_API=1 python -m unittest tests.query.test_live -v'''
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from API_integrations import catalog_client as cc

from .. import REAL_ENV
from .support import fixture, quiet

LIVE = REAL_ENV.get('HVLA_LIVE_API') == '1'
GATE = cc.STATE_PATH   #read at import, before any offline test swaps in a private gate
TOLERANCE = {'ra': 1 / 3600, 'dec': 1 / 3600, 'redshift': 1e-3}
KEPT = 0.9             #share of captured rows or ids a live answer must still have

#fixture -> the call that captured it, and its parser
QUERIES = {'ned_lookup_3C15': (cc.ned_lookup, '3C 15', cc._parse_lookup),
           'ned_lookup_3C58': (cc.ned_lookup, '3C 58', cc._parse_lookup),
           'ned_lookup_unknown': (cc.ned_lookup, '3C 999', cc._parse_lookup),
           'ned_photometry_3C15': (cc.ned_photometry, '3C 15', cc._parse_photometry),
           'simbad_resolve_3C15': (cc.simbad_resolve, '3C 15', cc._parse_simbad),
           'simbad_resolve_3C015': (cc.simbad_resolve, '3C 015', cc._parse_simbad),
           'simbad_resolve_unknown': (cc.simbad_resolve, '3C 999', cc._parse_simbad)}

def kept(live, captured):
  '''Share of the captured items the live answer still has.'''
  have = {json.dumps(x) for x in live}
  return sum(json.dumps(x) in have for x in captured) / len(captured)


@unittest.skipUnless(LIVE, 'HVLA_LIVE_API=1 sends these to NED and SIMBAD')
class TestLiveQueries(unittest.TestCase):
  '''Real gate, pacing forced on, an empty cache and the user's own proxy settings. A request
  past the budget raises instead of sending; a paused service skips its queries.'''
  sent, answer = 0, None   #requests this run; this test's response

  @classmethod
  def setUpClass(cls):
    cls.dir = Path(tempfile.mkdtemp(prefix='hvla-live-'))
    real = cc._session.request
    def request(method, url, **kw):
      if cls.sent >= len(QUERIES):
        raise AssertionError(f'live budget of {len(QUERIES)} requests spent; not sent')
      cls.sent += 1
      cls.answer = real(method, url, **kw)
      return cls.answer
    for patcher in (mock.patch.dict(os.environ, REAL_ENV, clear=True),
                    mock.patch.multiple(cc, PACE_REQUESTS=True, STATE_PATH=GATE, _announced=set(),
                                        CACHE_PATH=cls.dir / 'cache.sqlite'),
                    mock.patch.object(cc._session, 'request', request)):
      patcher.start()
      cls.addClassCleanup(patcher.stop)

  def setUp(self):
    type(self).answer = None
    cc._announced.clear()

  def save(self, key):
    '''Keeps this test's response as <dir>/<fixture>.xml; returns a note naming it.'''
    if self.answer is None:
      return ''
    path = self.dir / f'{key}.xml'
    path.write_bytes(self.answer.content)
    return f' (live answer: {path})'

  def send(self, key):
    '''QUERIES[key] sent for real: (parsed answer, note naming the saved response).'''
    fn, name, _ = QUERIES[key]
    sent = self.sent
    try:
      value, out = quiet(fn, name)
    except Exception as e:
      self.fail(f'{e!r}{self.save(key)}')
    note, out = self.save(key), out.strip()
    if self.sent == sent:
      self.skipTest(out)
    if self.answer is None:
      self.fail(out)
    self.assertEqual(self.answer.status_code, 200, out + note)
    return value, note

  def check(self, key):
    '''The live answer reads as the captured one did, allowing for catalog updates.'''
    live, note = self.send(key)
    captured = QUERIES[key][2](fixture(key))
    if not captured:
      self.assertFalse(live, f'no longer not found{note}')
    elif isinstance(captured, list):
      self.assertGreaterEqual(kept(live, captured), KEPT, f'{len(live)} rows{note}')
    else:
      self.assertTrue(live, f'no longer found{note}')
      self.assertEqual(set(live), set(captured), note)
      for field, want in captured.items():
        got, msg = live[field], f'{field}{note}'
        if field == 'ids':
          self.assertGreaterEqual(kept(got, want), KEPT, msg)
        elif field in TOLERANCE and None not in (got, want):
          self.assertAlmostEqual(got, want, delta=TOLERANCE[field], msg=msg)
        else:
          self.assertEqual(got, want, msg)

  def test_ned_lookup_3C15(self):
    self.check('ned_lookup_3C15')

  def test_ned_lookup_3C58(self):
    self.check('ned_lookup_3C58')

  def test_ned_lookup_unknown(self):
    self.check('ned_lookup_unknown')

  def test_ned_photometry_3C15(self):
    self.check('ned_photometry_3C15')

  def test_simbad_resolve_3C15(self):
    self.check('simbad_resolve_3C15')

  def test_simbad_resolve_3C015(self):
    self.check('simbad_resolve_3C015')

  def test_simbad_resolve_unknown(self):
    self.check('simbad_resolve_unknown')
