#from pre_calibration import *
#from pre_calibration.options_class import Options
from astroquery.simbad import Simbad
from pprint import pp 
from astropy.table import Table
import numpy as np

class simbad:
  '''functions for simbad integration'''
  def validate_source(source_name):
    if (simbad.get_all_names(source_name)) is False:
      return False
    return True

  def query_simbad():
    """
    Query Simbad to check a source exists 
    """
    print("Querying Simbad for source")
    source4c = "4c35.03"
    sourceB1950 = ""
    result = Simbad.query_objectids(source4c)#options.source_name)
    for row in range(len(result)):
      print(result[row])
    print(result)
    print(f"{type(result)}")

  def get_all_names(source_name):
    """
    Get all names for a source from Simbad
    returns False if source not found, else returns table of names
    """
    
    result = Simbad.query_objectids(source_name)
    if simbad.check_result(result) is False:
      return False
      #raise ValueError(f"Source {source_name} not found in Simbad.")
    return result

  def check_result(result):
    """
    Check if the result from Simbad is valid
    """
    if result is None or len(result) == 0:
      return False
    return True

if __name__ == "__main__":
  name = "4c35.03"
  x = simbad
  simbad.validate_source(source_name=name)
  #print(x1)