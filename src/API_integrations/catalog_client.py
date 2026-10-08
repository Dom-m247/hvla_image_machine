'''SIMBAD/NED client. Every request passes one host-wide gate, at most one request send per
INTERVAL_NS across all processes, and a per-user SQLite cache. Nothing else in the
project may send to these services.'''
import fcntl
import io
import json
import math
import os
import sqlite3
import subprocess
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import quote, urlencode

import numpy
import requests
from astropy.io import votable
from requests.adapters import HTTPAdapter

PACE_REQUESTS = True                         #False skips the 5 s wait; requests still go one at a time

INTERVAL_NS = 5 * 10**9                      #720 an hour at most: under 1,000 an hour
STATE_PATH = '/tmp/hvla_catalog_gate.json'   #fixed on purpose: a second path is a second gate
CACHE_PATH = Path.home() / '.cache' / 'hvla' / 'catalog.sqlite'
DAY = 86400
TTL_FOUND, TTL_PHOTOMETRY, TTL_NOT_FOUND = 90 * DAY, 30 * DAY, 7 * DAY
NED_URL = 'https://ned.ipac.caltech.edu/NED::API/'
NED_NOT_FOUND = 'Failed to resolve input object name'   #QUERY_STATUS text for an unknown name
#tried in order, a later entry only after an outage
SIMBAD_TAP = {'simbad-cds': 'https://simbad.cds.unistra.fr/simbad/sim-tap/sync'}
SIMBAD_QUERY = ("SELECT basic.main_id, basic.ra, basic.dec, ids.ids FROM ident AS lookup "
                "JOIN basic ON basic.oid = lookup.oidref JOIN ids ON ids.oidref = basic.oid "
                "WHERE lookup.id = '{}'")
REPO_URL = 'https://github.com/domo4448/hvla_image_machine'


#--- gate ---------------------------------------------------------------------

class Unavailable(Exception):
  '''endpoint or whole service is in a shared cooldown (blocked, rate-limited or unreachable)'''
  def __init__(self, key, until):
    super().__init__(f"{key} paused until {time.strftime('%H:%M', time.localtime(until))}")
    self.key, self.until = key, until

def _boot_id():
  with open('/proc/sys/kernel/random/boot_id') as f:
    return f.read().strip()

def _now_ns():
  return time.clock_gettime_ns(time.CLOCK_MONOTONIC)

def _open_state():
  flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
  while True:
    #plain open first: under fs.protected_regular, O_CREAT on another user's /tmp file is EACCES
    try:
      return os.open(STATE_PATH, flags)
    except FileNotFoundError:
      pass
    try:
      fd = os.open(STATE_PATH, flags | os.O_CREAT | os.O_EXCL, 0o666)
    except FileExistsError:
      continue                            #lost the create race; open the winner's file
    os.fchmod(fd, 0o666)                  #umask strips the bits other users' installs need
    return fd

def _still_at_path(fd):
  try:
    return os.path.samestat(os.stat(STATE_PATH, follow_symlinks=False), os.fstat(fd))
  except FileNotFoundError:
    return False

def _read(fd):
  try:
    state = json.loads(os.pread(fd, 65536, 0) or b'{}')
    return state if isinstance(state, dict) else {}
  except ValueError:
    return {}

def _write(fd, state):
  data = json.dumps(state).encode()
  os.pwrite(fd, data, 0)
  os.ftruncate(fd, len(data))

_pacing_warned = False

class slot:
  '''with slot('ned-lookup') as s: <one HTTP request>. Held for the whole exchange; endpoints
  are '<service>-<name>'. If recheck() returns something inside the lock, the slot is
  released unused and s.cached holds it.'''
  def __init__(self, endpoint, recheck=None):
    self.endpoint = endpoint
    self.service = endpoint.split('-')[0]
    self.recheck = recheck
    self.cached = None

  def __enter__(self):
    while True:
      fd = _open_state()
      try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        #the path may have been replaced while we waited; a lock on an orphaned file guards nothing
        if _still_at_path(fd):
          self.fd = fd
          self._claim()
          return self
      except BaseException:
        os.close(fd)                      #left open, it would hold the lock as long as this process lives
        raise
      os.close(fd)

  def _claim(self):
    global _pacing_warned
    self.state = _read(self.fd)
    cooldowns = self.state.get('cooldown')
    if isinstance(cooldowns, dict):
      for key in (self.endpoint, self.service):
        if (until := cooldowns.get(key, 0)) > time.time():
          raise Unavailable(key, until)
    if self.recheck and (hit := self.recheck()) is not None:
      self.cached = hit
      return
    boot = _boot_id()
    last = self.state.get('last_send_ns')
    if self.state.get('boot') == boot and isinstance(last, int):
      wait_ns = last + INTERVAL_NS - _now_ns()
    elif self.state.get('boot') and self.state.get('boot') != boot:
      wait_ns = 0                         #last request was before a reboot
    else:
      wait_ns = INTERVAL_NS               #new or unreadable file: assume a request just went out
    if not PACE_REQUESTS and not _pacing_warned:
      _pacing_warned = True
      print("catalog_client: PACE_REQUESTS is off; requests are not spaced 5 s apart")
    if wait_ns > 0 and PACE_REQUESTS:
      time.sleep(wait_ns / 1e9)
    self.state.update(boot=boot, last_send_ns=_now_ns())
    _write(self.fd, self.state)           #stamped before sending: a request that dies mid-flight counts

  def cool_down(self, seconds, whole_service=False):
    '''Every process skips this endpoint, or every endpoint of its service, until then.'''
    cooldowns = self.state.get('cooldown')
    if not isinstance(cooldowns, dict):
      cooldowns = self.state['cooldown'] = {}
    cooldowns[self.service if whole_service else self.endpoint] = time.time() + seconds
    _write(self.fd, self.state)

  def __exit__(self, *exc):
    os.close(self.fd)                     #closing releases the flock; so does process death
    return False


#--- cache --------------------------------------------------------------------

def _normalize(name):
  return ' '.join(str(name).split())

def _db():
  CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
  db = sqlite3.connect(CACHE_PATH, timeout=30)
  db.execute('PRAGMA journal_mode=WAL')
  db.execute('CREATE TABLE IF NOT EXISTS entries (key TEXT PRIMARY KEY, value TEXT NOT NULL, '
             'fetched REAL NOT NULL, expires REAL NOT NULL)')
  return db

def _cache_get(key):
  '''Stored value for key, or None when missing or expired.'''
  with closing(_db()) as db:
    row = db.execute('SELECT value FROM entries WHERE key = ? AND expires > ?',
                     (key, time.time())).fetchone()
  return json.loads(row[0]) if row else None

def _cache_put(key, value, ttl):
  now = time.time()
  with closing(_db()) as db, db:
    db.execute('INSERT OR REPLACE INTO entries VALUES (?, ?, ?, ?)',
               (key, json.dumps(value), now, now + ttl))


#--- the one place that sends -------------------------------------------------

def _version():
  try:
    out = subprocess.run(['git', '-C', str(Path(__file__).resolve().parent), 'rev-parse', '--short', 'HEAD'],
                         capture_output=True, text=True, timeout=5)
    return out.stdout.strip() or 'unknown'
  except (OSError, subprocess.SubprocessError):
    return 'unknown'

USER_AGENT = f'hvla_image_machine/{_version()} (+{REPO_URL})'

_session = requests.Session()
_session.headers['User-Agent'] = USER_AGENT
_session.mount('https://', HTTPAdapter(max_retries=0))   #no hidden urllib3 retries

def _retry_after(r, default):
  try:
    return max(60, int(r.headers['Retry-After']))
  except (KeyError, ValueError):
    return default

def send(s, method, url, *, timeout, **kwargs):
  '''The one place that talks to SIMBAD/NED; call it only inside `with slot(...) as s`.'''
  try:
    #redirects off: a followed redirect is a second request the gate never saw
    r = _session.request(method, url, timeout=timeout, allow_redirects=False, **kwargs)
  except requests.RequestException:
    s.cool_down(300)
    raise
  if r.status_code == 403:
    s.cool_down(24 * 3600, whole_service=True)   #blocked: stop asking every server of this service
  elif r.status_code == 429:
    s.cool_down(_retry_after(r, default=600), whole_service=True)
  elif r.status_code == 503:
    s.cool_down(_retry_after(r, default=600))
  return r

_announced = set()   #cooldown keys this process has already reported

def _attempt(endpoint, key, parser, ttl, label, method, url, **kwargs):
  '''One try at one endpoint: (value, outage). value is the parsed result, empty when the
  service does not know the name; outage means another server may still answer.'''
  try:
    with slot(endpoint, recheck=lambda: _cache_get(key)) as s:
      if s.cached is not None:
        return s.cached, False
      r = send(s, method, url, **kwargs)
      if r.status_code != 200:
        print(f"{label} ({endpoint}) failed: HTTP {r.status_code}")
        return None, r.status_code >= 500
      value = parser(r.content)
      _cache_put(key, value, ttl if value else TTL_NOT_FOUND)   #before release, so waiting processes find it
      return value, False
  except Unavailable as e:
    if e.key not in _announced:
      _announced.add(e.key)
      print(f"{e}; answering 'unknown' until then")
    return None, True
  except requests.RequestException as e:
    print(f"{label} ({endpoint}) failed: {e}")
    return None, True

def _fetch(key, parser, ttl, label, attempts, **kwargs):
  '''Cached request over attempts [(endpoint, method, url)], tried in order, the next only
  after an outage. The parsed result, or None when no endpoint could answer.'''
  if (hit := _cache_get(key)) is not None:
    return hit
  for endpoint, method, url in attempts:
    value, outage = _attempt(endpoint, key, parser, ttl, label, method, url, **kwargs)
    if not outage:
      return value
  return None


#--- VOTable answers ----------------------------------------------------------

def _number(value):
  '''float(value), or None when masked, empty or NaN.'''
  if value is None or numpy.ma.is_masked(value):
    return None
  try:
    value = float(value)
  except (TypeError, ValueError):
    return None
  return None if math.isnan(value) else value

def _votable_table(body, not_found=None):
  '''First table of a VOTable answer, or None when its QUERY_STATUS error says not_found.'''
  doc = votable.parse(io.BytesIO(body), verify='ignore')
  for status in [*doc.params, *doc.infos, *(s for r in doc.resources for s in (*r.params, *r.infos))]:
    if status.name == 'QUERY_STATUS' and status.value == 'ERROR':
      #PARAM carries its text in description (NED), INFO in content (TAP)
      text = getattr(status, 'description', None) or getattr(status, 'content', None) or 'query failed'
      if not_found and not_found in text:
        return None
      raise ValueError(' '.join(str(text).split()))
  return doc.get_first_table().to_table(use_names_over_ids=True)


#--- NED ----------------------------------------------------------------------

def _parse_lookup(body):
  rows = _votable_table(body, NED_NOT_FOUND)
  if rows is None or len(rows) == 0:
    return {}
  if len(rows) > 1:
    raise ValueError(f"NED returned {len(rows)} objects for one name")
  row = rows[0]
  ra, dec = _number(row['RA']), _number(row['Dec'])
  if ra is None or dec is None:
    raise ValueError("NED returned no position")
  return {'name': str(row['Object Name']), 'ra': ra, 'dec': dec,
          'redshift': _number(row['Redshift (z)'])}

def _parse_photometry(body):
  if (table := _votable_table(body, NED_NOT_FOUND)) is None:
    return []
  rows = []
  for row in table:
    freq, flux = _number(row['Frequency (Hz)']), _number(row['Flux Density'])
    if freq is not None and flux is not None:
      rows.append([freq, flux])
  return rows

def _ned(endpoint, key, service, params, parser, ttl, timeout):
  return _fetch(key, parser, ttl, f"NED {service} for '{params['TARGET']}'", [(endpoint, 'GET', NED_URL + service)],
                params=urlencode(params, quote_via=quote), timeout=timeout)

def ned_lookup(name):
  '''{'name', 'ra', 'dec', 'redshift'} for an object (redshift None when NED has none),
  or None when NED does not know the name or cannot answer.'''
  if not (name := _normalize(name)):
    return None
  return _ned('ned-lookup', f'ned:lookup:{name}', 'ConeSearchByTarget',
              {'TARGET': name, 'RADIUS': 0}, _parse_lookup, TTL_FOUND, (10, 30)) or None

def ned_photometry(name):
  '''[freq_hz, flux_jy] rows of NED's broadband photometry ([] when it has none), or
  None when NED cannot answer.'''
  if not (name := _normalize(name)):
    return None
  return _ned('ned-photometry', f'ned:phot:{name}', 'PhotometryOfObject',
              {'TARGET': name}, _parse_photometry, TTL_PHOTOMETRY, (10, 60))


#--- SIMBAD -------------------------------------------------------------------

def _parse_simbad(body):
  rows = _votable_table(body)
  if rows is None or len(rows) == 0:
    return {}
  if len(rows) > 1:
    raise ValueError(f"SIMBAD returned {len(rows)} objects for one name")
  row = rows[0]
  return {'main_id': str(row['main_id']).strip(), 'ra': _number(row['ra']), 'dec': _number(row['dec']),
          'ids': [i.strip() for i in str(row['ids']).split('|') if i.strip()]}

def simbad_resolve(name):
  '''{'main_id', 'ra', 'dec', 'ids'} for an object (ra/dec None when SIMBAD has no position),
  or None when SIMBAD does not know the name or cannot answer.'''
  if not (name := _normalize(name)):
    return None
  form = {'REQUEST': 'doQuery', 'LANG': 'ADQL', 'FORMAT': 'votable',
          'QUERY': SIMBAD_QUERY.format(name.replace("'", "''"))}
  return _fetch(f'simbad:resolve:{name}', _parse_simbad, TTL_FOUND, f"SIMBAD for '{name}'",
                [(endpoint, 'POST', url) for endpoint, url in SIMBAD_TAP.items()],
                data=form, timeout=(10, 30)) or None
