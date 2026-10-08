'''SIMBAD through catalog_client and simbad.py, on CDS answers captured 2026-10-06, plus
the ordered-attempts (mirror) logic against a stand-in mirror.'''
import unittest

import requests
from API_integrations import catalog_client as cc
from API_integrations.simbad import simbad

from .support import CatalogTestCase, answer, fixture, quiet, raises

CDS = cc.SIMBAD_TAP['simbad-cds']
MIRROR = 'https://mirror.invalid/simbad/sim-tap/sync'
WITH_MIRROR = {'simbad-cds': CDS, 'simbad-mirror': MIRROR}
SIMBAD_3C15 = fixture('simbad_resolve_3C15')
SIMBAD_UNKNOWN = fixture('simbad_resolve_unknown')
NED_3C15 = fixture('ned_lookup_3C15')
NED_UNKNOWN = fixture('ned_lookup_unknown')
POSITION = (9.26712805076, -1.15233546361)
NED_POSITION = (9.2671047, -1.1522973)

#CDS response -> servers asked, cooldowns left, whether the mirror's answer comes back
MIRROR_CASES = [
    ('CDS timeout', raises(requests.ReadTimeout('read timed out')), ['cds', 'mirror'], {'simbad-cds': 300}, True),
    ('CDS 503', answer(503), ['cds', 'mirror'], {'simbad-cds': 600}, True),
    ('CDS 500', answer(500), ['cds', 'mirror'], {}, True),
    ('CDS 403', answer(403), ['cds'], {'simbad': 86400}, False),
    ('CDS 429', answer(429), ['cds'], {'simbad': 600}, False),
    ('CDS 400', answer(400), ['cds'], {}, False),
    ('CDS not found', answer(200, SIMBAD_UNKNOWN), ['cds'], {}, False)]


class SimbadTestCase(CatalogTestCase):
  def route(self, cds, mirror=None, ned=None, tap=None):
    '''Answer per server, with tap as the SIMBAD endpoints; returns the servers asked, in order.'''
    if tap:
      cc.SIMBAD_TAP = tap
    servers = {CDS: ('cds', cds), MIRROR: ('mirror', mirror)}
    asked = []
    def respond(method, url, kw):
      server, responder = servers.get(url, ('ned', ned))
      asked.append(server)
      return responder(method, url, kw)
    self.serve(respond)
    return asked


class TestSimbadParsers(unittest.TestCase):
  def test_3C15(self):
    found = cc._parse_simbad(SIMBAD_3C15)
    self.assertEqual(found['main_id'], '3C  15')
    self.assertEqual((found['ra'], found['dec']), POSITION)
    self.assertEqual(len(found['ids']), 49)
    self.assertIn('PKS 0034-01', found['ids'])

  def test_ned_alias_form_is_the_same_object(self):
    self.assertEqual(cc._parse_simbad(fixture('simbad_resolve_3C015')), cc._parse_simbad(SIMBAD_3C15))

  def test_unknown_name_is_not_found(self):
    self.assertEqual(cc._parse_simbad(SIMBAD_UNKNOWN), {})


class TestSimbadRequest(CatalogTestCase):
  def test_posts_the_combined_query_to_cds(self):
    calls = self.serve(answer(200, SIMBAD_3C15))
    quiet(cc.simbad_resolve, '3C 15')
    [(method, url, kw)] = calls
    self.assertEqual((method, url, kw['timeout']), ('POST', CDS, (10, 30)))
    self.assertEqual(kw['data'], {'REQUEST': 'doQuery', 'LANG': 'ADQL', 'FORMAT': 'votable',
                                  'QUERY': cc.SIMBAD_QUERY.format('3C 15')})

  def test_quotes_doubled_and_whitespace_collapsed(self):
    calls = self.serve(answer(200, SIMBAD_UNKNOWN))
    quiet(cc.simbad_resolve, "O'Neil   1")
    self.assertEqual(calls[0][2]['data']['QUERY'], cc.SIMBAD_QUERY.format("O''Neil 1"))


class TestSimbadWrapper(SimbadTestCase):
  def test_names_and_coordinates_share_one_request(self):
    asked = self.route(answer(200, SIMBAD_3C15))
    names, _ = quiet(simbad.formatted_names_list, '3C 015')
    pos, _ = quiet(simbad.coordinates, '3C 015')
    self.assertIsInstance(names, list)
    self.assertLessEqual({'3C15', 'PKS0034-01', '0034-01'}, set(names))
    self.assertEqual(pos, POSITION)
    self.assertEqual(asked, ['cds'])

  def test_unknown_to_simbad_takes_ned_position_and_no_names(self):
    asked = self.route(answer(200, SIMBAD_UNKNOWN), ned=answer(200, NED_3C15))
    pos, out = quiet(simbad.coordinates, '3C 999')
    names, _ = quiet(simbad.formatted_names_list, '3C 999')
    self.assertEqual(pos, NED_POSITION)
    self.assertIn("using NED's", out)
    self.assertIs(names, False)
    self.assertEqual(asked, ['cds', 'ned'])

  def test_blocked_takes_ned_position_and_pauses_simbad(self):
    self.route(answer(403), ned=answer(200, NED_3C15))
    self.assertEqual(quiet(simbad.coordinates, '3C 15')[0], NED_POSITION)
    self.assertCooldowns({'simbad': 86400})

  def test_neither_knows_the_name(self):
    self.route(answer(200, SIMBAD_UNKNOWN), ned=answer(200, NED_UNKNOWN))
    self.assertIsNone(quiet(simbad.coordinates, '3C 999')[0])

  def test_malformed_answer_is_reported_not_raised(self):
    self.route(answer(200, b'not a votable'), ned=answer(200, NED_UNKNOWN))
    pos, out = quiet(simbad.coordinates, '3C 15')
    names, _ = quiet(simbad.formatted_names_list, '3C 15')
    self.assertIsNone(pos)
    self.assertIs(names, False)
    self.assertIn('Catalog query failed', out)


class TestMirror(SimbadTestCase):
  def test_mirror_asked_only_after_a_cds_outage(self):
    found = cc._parse_simbad(SIMBAD_3C15)
    for label, cds, want_asked, want_cooldowns, answered in MIRROR_CASES:
      with self.subTest(label):
        self.fresh()
        asked = self.route(cds, mirror=answer(200, SIMBAD_3C15), tap=WITH_MIRROR)
        value, _ = quiet(cc.simbad_resolve, '3C 15')
        self.assertEqual(asked, want_asked)
        self.assertCooldowns(want_cooldowns)
        self.assertEqual(value, found if answered else None)

  def test_next_name_while_cds_cools_goes_straight_to_the_mirror(self):
    asked = self.route(raises(requests.ReadTimeout('read timed out')), mirror=answer(200, SIMBAD_3C15), tap=WITH_MIRROR)
    quiet(cc.simbad_resolve, '3C 15')
    quiet(cc.simbad_resolve, '3C 48')
    self.assertEqual(asked, ['cds', 'mirror', 'mirror'])

  def test_block_sends_nothing_anywhere_afterwards(self):
    asked = self.route(answer(403), mirror=answer(200, SIMBAD_3C15), tap=WITH_MIRROR)
    quiet(cc.simbad_resolve, '3C 15')
    quiet(cc.simbad_resolve, '3C 48')
    self.assertEqual(asked, ['cds'])

  def test_both_down_pauses_both_and_sends_nothing_more(self):
    asked = self.route(raises(requests.ReadTimeout('cds down')), mirror=raises(requests.ReadTimeout('mirror down')),
                       tap=WITH_MIRROR)
    self.assertIsNone(quiet(cc.simbad_resolve, '3C 15')[0])
    self.assertCooldowns({'simbad-cds': 300, 'simbad-mirror': 300})
    quiet(cc.simbad_resolve, '3C 48')
    self.assertEqual(asked, ['cds', 'mirror'])
