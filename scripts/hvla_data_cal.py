FULLMS = 'fullSet' #+".ms"
import casatasks as ct
import sys,os
from .data_class import data
#from .data_calibration import parse_list_obs as parse
from .data_calibration import *
import pprint as pp
from .constants import *

def build_setjy(options):
  #pp.pp(options.get_dict())
  visfile = AMP_CAL_MS+'.ms'
  amp_field = '1'
  #amp_field needs to be found int init.ms... woooooo MORE PAAARSING
  #for field in options.get_dict_sp("fields"): #can be done better...
  #  if field['src_id'] == options.get_dict_sp("amp_cal_source_id"):
  #    amp_field = amp_field + str(field['id'])
  #    print(f"{amp_field}")
  #    print(f"{type(amp_field)}")
  use_model = options.get_dict_sp("model") + ".im" #add +".im" to original add!
  ct.setjy(vis=visfile,field=amp_field,standard='Perley-Butler 2013',model=use_model,usescratch= True ,scalebychan=True,spw='')

def convert_to_ms(archive):
  """
  Converts raw HVLA data archive to Measurement Set (MS) format
  """
  #OUTPUT MS name = "fullMS.ms" -> weird cstring error if not directly entered.
  if (archive.endswith('.ms')):
    print(f"Archive {archive} is already in MS format.")
    archive = archive[:len(archive)-3]
    return parse.log_listobs(archive)
  #import archive to MS
  print(f"Converting archive {archive} to Measurement Set format...")
  try:
    if not os.path.exists(FULLMS+'.ms'):
      print("This may take a moment...",end="")
      ct.importvla(archivefiles={archive},vis=FULLMS+'.ms')
      print("Done")
    return parse.log_listobs(FULLMS)

  except RuntimeError as file_exists:
    print(f"MS file already exists, delete it and re-run")
    sys.exit() # add call to a cleanup script?

def pre_data_calibration(options):
  """extract and clean necessary info for data calibration"""
  list_obs = convert_to_ms(options.get_dict()['archive_file']) 
  
  #extract info from listobs -> more complete than returned data
  parse.parseListObs(list_obs,options) 

  #find calibrators TODO: add phase calibration option
  find_cal.find_amp_cal(options)
  print("running Amp Calibration...")
  cal_split.amp_cal_split(options)

def data_calibration(options):
  """
  main in for data calibration of HVLA data archive
  Creates MS files from raw data, applies calibration
  """
  pre_data_calibration(options)
  build_setjy(options)
  
  
