#from pre_calibration import *
#from pre_calibration.options_class import Options
from astroquery.simbad import Simbad
from pprint import pp 

def query_simbad():
  """
  Query Simbad to check a source exists 
  """
  print("Querying Simbad for source")
  source4c = "4c35.03"
  sourceB1950 = ""
  result = Simbad.query_objectids(source4c)#options.source_name)
  print(result)

if __name__ == "__main__":
  query_simbad()