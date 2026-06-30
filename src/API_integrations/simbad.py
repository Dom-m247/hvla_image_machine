#from pre_calibration import *
#from pre_calibration.options_class import Options
from astroquery.simbad import Simbad
from pprint import pp 
from astropy.table import Table
import numpy as np
import re

class simbad:
  '''functions for simbad integration'''
  @staticmethod
  def validate_source(source_name):
    if (simbad.get_all_names(source_name)) is False:
      return False
    return True

  #def query_simbad():
  #  """
  #  Query Simbad to check a source exists 
  #  """
  #  print("Querying Simbad for source")
  #  source4c = "4c35.03"
  #  sourceB1950 = ""
  #  result = Simbad.query_objectids(source4c)#options.source_name)
  #  for row in range(len(result)):
  #    print(result[row])
  #  print(result)
  #  print(f"{type(result)}")

  @staticmethod
  def get_all_names(source_name):
    """
    Get all names for a source from Simbad
    returns False if source not found, else returns table of names
    """
    
    result = Simbad.query_objects(source_name)
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
  def formatted_names_list(source_name):
    '''Given a SIMBAD-resolvable source name, return a list of candidate alias
    strings to compare against listobs field names.

    listobs names have no internal spaces and are either catalog designations
    ('3C15') or coordinate strings ('0034-014'); SIMBAD aliases are spaced and
    often prefixed ('3C 15', 'PKS 0034-01', '[HB89] 0034-014'). For each alias
    we therefore emit two candidates so either style can match:
      - compact:    bracketed tags + whitespace removed, letters kept
                    ('3C 15' -> '3C15')
      - coordinate: keep only digits, '+', '-', '.'
                    ('PKS 0034-01' -> '0034-01')
    Returns False if SIMBAD cannot resolve the name.
    '''
    result = Simbad.query_objectids(source_name)
    if (simbad.check_result(result) is False):
      return False
    all_names = []
    for each_id in result:
      raw = str(each_id)
      cleaned = re.sub(r'[\[\{].*?[\]\}]', '', raw)            # drop [HB89]/{...} catalog tags
      compact = re.sub(r'\s+', '', cleaned).strip()            # '3C 15' -> '3C15'
      coord = re.sub(r'[^0-9+\-.]', '', cleaned).strip('+-.')  # 'PKS 0034-01' -> '0034-01'
      for candidate in (compact, coord):
        if candidate and candidate not in all_names:
          all_names.append(candidate)
    return all_names