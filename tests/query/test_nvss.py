'''NVSS cone searches through catalog_client, on HEASARC's answer captured 2026-11-12 (all
columns, within 0.25 deg of M87).'''
import unittest

from API_integrations import catalog_client as cc

from .support import CatalogTestCase, answer, fixture, quiet

CONE = fixture('nvss_heasarc_m87')
EMPTY = b'''<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/><TABLE>
<FIELD name="ra" datatype="double" unit="deg"/><FIELD name="dec" datatype="double" unit="deg"/>
<FIELD name="flux_20_cm" datatype="double" unit="mJy"/>
<DATA><TABLEDATA></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>'''
ERROR = b'''<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="ERROR">Unknown table</INFO></RESOURCE></VOTABLE>'''


class TestParser(unittest.TestCase):
  def test_degrees_and_mjy_to_jy(self):
    rows = cc._parse_nvss(CONE)
    self.assertEqual(len(rows), 27)
    m87 = max(rows, key=lambda r: r[2])
    self.assertAlmostEqual(m87[0], 187.70608333)
    self.assertAlmostEqual(m87[1], 12.38933333)
    self.assertAlmostEqual(m87[2], 138.487)

  def test_no_sources_and_errors(self):
    self.assertEqual(cc._parse_nvss(EMPTY), [])
    with self.assertRaises(ValueError):
      cc._parse_nvss(ERROR)


class TestCone(CatalogTestCase):
  def test_one_request_then_the_cache(self):
    calls = self.serve(answer(200, CONE))
    first, _ = quiet(cc.nvss_sources, 187.70593, 12.39112, 0.25)
    again, _ = quiet(cc.nvss_sources, 187.70593, 12.39112, 0.25)
    self.assertEqual(first, again)
    self.assertEqual(len(calls), 1)
    method, url, kw = calls[0]
    self.assertEqual((method, url), ('POST', cc.HEASARC_TAP))
    self.assertIn("CIRCLE('ICRS', 187.70593, 12.39112, 0.2500)", kw['data']['QUERY'])
    self.assertFalse(kw['allow_redirects'])

  def test_an_outage_answers_none_and_cools_down(self):
    calls = self.serve(answer(503))
    value, _ = quiet(cc.nvss_sources, 10.0, 20.0, 0.5)
    self.assertIsNone(value)
    self.assertEqual(len(calls), 1)
    self.assertCooldowns({'heasarc-nvss': 600})


if __name__ == '__main__':
  unittest.main()
