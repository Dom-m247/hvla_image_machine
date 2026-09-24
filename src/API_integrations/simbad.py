#from pre_calibration import *
#from pre_calibration.options_class import Options
from astroquery.simbad import Simbad
from pprint import pp 
from astropy.table import Table
from typing import cast
import numpy as np
import re
import threading

#astroquery sends SIMBAD queries through pyvo's TAP client, which sets no network
#timeout (astroquery's own 'timeout' is the server-side execution limit): an
#unreachable SIMBAD holds a call for minutes. Each call gets this long instead.
SIMBAD_TIMEOUT_S = 20
_unreachable = False   #set by the first timeout; later calls skip SIMBAD for the run

def _query(label, call, *args):
  """call(*args) with a hard time limit. None when SIMBAD fails or does not answer."""
  global _unreachable
  if _unreachable:
    return None
  outcome = {}
  def run():
    try:
      outcome['result'] = call(*args)
    except Exception as exc:
      outcome['error'] = exc
  #daemon: a call that never returns must not keep the process alive at exit
  worker = threading.Thread(target=run, daemon=True)
  worker.start()
  worker.join(SIMBAD_TIMEOUT_S)
  if worker.is_alive():
    _unreachable = True
    print(f"SIMBAD did not answer ({label}) within {SIMBAD_TIMEOUT_S}s; "
          f"continuing without it for the rest of this run.")
    return None
  if 'error' in outcome:
    print(f"SIMBAD query failed ({label}): {outcome['error']}")
    return None
  return outcome.get('result')

class simbad:
  '''functions for simbad integration'''
  @staticmethod
  def validate_source(source_name):
    if (simbad.get_all_names(source_name)) is False:
      return False
    return True

  @staticmethod
  def get_all_names(source_name):
    """
    Get all names for a source from Simbad
    returns False if source not found (or SIMBAD unreachable), else returns table of names
    """
    
    result = _query(f"names of {source_name}", Simbad.query_objects, source_name)
    if (simbad.check_result(result) is False):
      return False
      #raise ValueError(f"Source {source_name} not found in Simbad.")
    return result

  @staticmethod
  def check_result(result):
    """
    Check if the result from Simbad is valid
    """
    if result is None or len(result) == 0:
      return False
    return True

  @staticmethod
  def coordinates(source_name):
    '''(ra_deg, dec_deg) for a source, or None when SIMBAD cannot resolve it or be reached.'''
    result = _query(f"position of {source_name}", Simbad.query_object, source_name)
    if result is None or simbad.check_result(result) is False:
      return None
    try:
      return float(result[0]['ra']), float(result[0]['dec'])
    except (TypeError, ValueError):
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
    result = cast(Table, _query(f"aliases of {source_name}", Simbad.query_objectids, source_name))
    if (simbad.check_result(result) is False):
      return False
    all_names = []
    for each_id in result[result.colnames[0]]:
      raw = str(each_id)
      cleaned = re.sub(r'[\[\{].*?[\]\}]', '', raw)            # drop [HB89]/{...} catalog tags
      compact = re.sub(r'\s+', '', cleaned).strip()            # '3C 15' -> '3C15'
      coord = re.sub(r'[^0-9+\-.]', '', cleaned).strip('+-.')  # 'PKS 0034-01' -> '0034-01'
      for candidate in (compact, coord):
        if candidate and candidate not in all_names:
          all_names.append(candidate)
    return all_names