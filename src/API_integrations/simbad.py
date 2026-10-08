#from pre_calibration import *
#from pre_calibration.options_class import Options
from API_integrations.catalog_client import ned_lookup, simbad_resolve
import re

def _safe(lookup, source_name):
  '''lookup(source_name), with a malformed answer reported and read as None.'''
  try:
    return lookup(source_name)
  except Exception as e:
    print(f"Catalog query failed for {source_name}: {e}")
    return None

class simbad:
  '''functions for simbad integration'''
  @staticmethod
  def coordinates(source_name):
    '''(ra_deg, dec_deg) for a source, NED's when SIMBAD has none; None when neither
    can resolve it or be reached.'''
    found = _safe(simbad_resolve, source_name)
    if found and found['ra'] is not None and found['dec'] is not None:
      return found['ra'], found['dec']
    if ned := _safe(ned_lookup, source_name):
      print(f"SIMBAD has no position for {source_name}; using NED's")
      return ned['ra'], ned['dec']
    return None

  @staticmethod
  def formatted_names_list(source_name):
    '''Candidate alias strings for a source, to match against listobs field names.

    listobs names have no internal spaces and are either catalog designations
    ('3C15') or coordinate strings ('0034-014'), while SIMBAD aliases are spaced
    and often prefixed ('[HB89] 0034-014'), so each alias yields two candidates:
      - compact:    bracketed tags + whitespace removed ('3C 15' -> '3C15')
      - coordinate: digits, '+', '-', '.' only ('PKS 0034-01' -> '0034-01')
    Returns False if SIMBAD cannot resolve the name, or cannot be reached.
    '''
    found = _safe(simbad_resolve, source_name)
    if not found:
      return False
    all_names = []
    for raw in found['ids']:
      cleaned = re.sub(r'[\[\{].*?[\]\}]', '', raw)            # drop [HB89]/{...} catalog tags
      compact = re.sub(r'\s+', '', cleaned).strip()            # '3C 15' -> '3C15'
      coord = re.sub(r'[^0-9+\-.]', '', cleaned).strip('+-.')  # 'PKS 0034-01' -> '0034-01'
      for candidate in (compact, coord):
        if candidate and candidate not in all_names:
          all_names.append(candidate)
    return all_names