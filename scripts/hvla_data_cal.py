FULLMS = 'fullSet' #+".ms"
import casatasks as ct
import sys,os
from .data_class import data
from .data_calibration import parse_list_obs as parse
import pprint as pp


def convert_to_ms(archive):
  """
  Converts raw HVLA data archive to Measurement Set (MS) format
  """
  #OUTPUT MS name = "fullMS.ms" -> weird cstring error if not directly entered.
  FULLMS = 'fullSet'
  if (archive.endswith('.ms')):
    print(f"Archive {archive} is already in MS format.")
    return
  #import archive to MS
  print(f"Converting archive {archive} to Measurement Set format...")
  try:
    if not os.path.exists(FULLMS+'.ms'):
      ct.importvla(archivefiles={archive},vis=FULLMS+'.ms')
    return parse.log_listobs(FULLMS)

  except RuntimeError as file_exists:
    print(f"Vis file already exists, delete it and re-run")
    sys.exit() # add call to a cleanup script?
    

def data_cal(options):
  """
  main in for data calibration of HVLA data archive
  Creates MS files from raw data, applies calibration
  """
  list_obs = convert_to_ms(options.get_dict()['archive_file']) 
  parse.parseListObs(list_obs,options) 



if __name__ == "__main__":
  #test run
  import scripts.import_settings as import_settings
  options = data()
  imported_setting = import_settings.import_options()
  options.add_dict(imported_setting)
  data_cal(options)