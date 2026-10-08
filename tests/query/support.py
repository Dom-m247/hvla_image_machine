'''Shared helpers: fake responses, captured fixtures, and a TestCase that isolates catalog_client.'''
import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from API_integrations import catalog_client as cc

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
FOUND_3C15 = {'name': '3C 015', 'ra': 9.2671047, 'dec': -1.1522973, 'redshift': 0.07367822}   #ned_lookup_3C15, parsed

def fixture(name):
  return (FIXTURES / f'{name}.xml').read_bytes()

class FakeResp:
  def __init__(self, status, content=b'', headers=None):
    self.status_code, self.content, self.headers = status, content, headers or {}

def answer(status, content=b'', headers=None):
  '''A responder that always gives this response.'''
  return lambda *_: FakeResp(status, content, headers)

def raises(exc):
  '''A responder that fails the way requests does.'''
  def respond(*_):
    raise exc
  return respond

def quiet(fn, *a):
  '''(fn(*a), what it printed)'''
  out = io.StringIO()
  with contextlib.redirect_stdout(out):
    value = fn(*a)
  return value, out.getvalue()

class CatalogTestCase(unittest.TestCase):
  '''Each test gets its own gate file and cache, pacing off (its one-time notice suppressed) and
  a session that refuses to send. Every catalog_client global is put back afterwards.'''
  def setUp(self):
    tmp = tempfile.TemporaryDirectory(prefix='hvla-catalog-tests-')
    self.addCleanup(tmp.cleanup)
    self.tmp = Path(tmp.name)
    for patcher in (mock.patch.multiple(cc, PACE_REQUESTS=False, _pacing_warned=True, _announced=set(),
                                        STATE_PATH=None, CACHE_PATH=None, SIMBAD_TAP=dict(cc.SIMBAD_TAP)),
                    mock.patch.object(cc._session, 'request')):
      patcher.start()
      self.addCleanup(patcher.stop)
    self.fresh()
    self.serve(raises(AssertionError('unexpected request')))

  def fresh(self):
    '''A new gate file and cache, as if nothing had been sent.'''
    d = Path(tempfile.mkdtemp(dir=self.tmp))
    cc.STATE_PATH, cc.CACHE_PATH = str(d / 'gate.json'), d / 'cache.sqlite'
    cc._announced.clear()

  def serve(self, respond):
    '''Answer each request with respond(method, url, kw); returns the (method, url, kw) sent.'''
    calls = []
    def request(method, url, **kw):
      calls.append((method, url, kw))
      return respond(method, url, kw)
    cc._session.request = request
    return calls

  def assertCooldowns(self, want):
    '''The gate file holds exactly these cooldowns, each within 5 s of the seconds given.'''
    path = Path(cc.STATE_PATH)
    stored = json.loads(path.read_text()).get('cooldown', {}) if path.exists() else {}
    left = {key: until - time.time() for key, until in stored.items()}
    self.assertEqual(set(left), set(want))
    for key, seconds in want.items():
      self.assertAlmostEqual(left[key], seconds, delta=5, msg=key)
